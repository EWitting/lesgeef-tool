import ortools.sat.python.cp_model as cp_model
import numpy as np
from datetime import date
from .config import RoosterConfig
from .models import Les, Lesgever, Planning, DatumPrikker
from .importer import distance

def schedule_lessons(datumprikker: DatumPrikker, config: RoosterConfig) -> None:
    """Optimaliseert rooster op basis van een aantal constraints, 
    vooral soft constraints, om rekening te houden met situaties waar een perfect rooster niet gemaakt kan worden.
    Gebruikt Google OR-Tools. Vult alleen de lessen in die in de datumprikker voorkomen.
    
    Lessen die niet doorgaan ("Geen les"):
    - Als een les in de planning gaat_door=False heeft, wordt deze overgeslagen
    - Deze lessen krijgen geen lesgevers toegewezen en blijven leeg
    - Ze worden niet meegenomen in constraints en optimalisatie
    
    Lessen in het verleden:
    - Als een les al geweest is (datum < vandaag), wordt de planning niet aangepast
    - Deze lessen blijven zoals ze zijn (behoud bestaande lesgevers of lege status)
    - Ze worden niet meegenomen in constraints en optimalisatie
    
    Pre-assigned Lesgevers:
    - Als een les in de geïmporteerde planning al lesgevers heeft, worden deze gefixeerd (harde constraint)
    - Pre-assigned lesgevers worden altijd behouden, zelfs als ze Nee hebben in de beschikbaarheid matrix
    - Pre-assigned lesgevers worden uitgesloten van bepaalde soft constraint penalties
    - Naam matching gebruikt fuzzy matching (Levenshtein distance < 3)
    
    Harde Constraints:
    - Alleen bij Ja of Misschien kan een lesgever worden ingedeeld (harde constraint)
    - Maximum aantal lesgevers per les (harde constraint)
    - Pre-assigned lesgevers MOETEN toegewezen blijven (harde constraint)
    
    Soft Constraints:
    - Minimum aantal lesgevers per les (soft constraint met penalty) (probeert dit eerst als harde constraint)
    - Minimaal 1 ervaren lesgever per les (soft constraint met penalty)
    - Geen lesgevers met Misschien (soft constraint met penalty)
    - Penalty voor meerdere lessen per week voor dezelfde lesgever (soft constraint met penalty)
    - Liever meer lesgevers (soft constraint met penalty)
    - Ongelijk verdeeldheid van lessen (soft constraint met penalty)

    Vult de lessen in die in de datumprikker voorkomen.
    """

    # Matrix met assignments als variabelen in de searchspace
    # Harde constraint dat beschikbaarheid niet Nee kan zijn 
    lesgevers = datumprikker.lesgevers_al_ingevuld
    model, assignments = _make_model(lesgevers, datumprikker, config, hard_min=True)
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("Geen oplossing gevonden met harde constraint!")
        print("Het rooster kan dus niet compleet gemaakt worden, nu wordt het zonder harde constraint geprobeerd.")
        model, assignments = _make_model(lesgevers, datumprikker, config, hard_min=False)
        status = solver.Solve(model)
        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("Geen oplossing gevonden!")
            return

    # Vul de planning in, dit kan door de Les objecten te updaten
    # Skip lessen die niet doorgaan (gaat_door == False) - die blijven leeg
    # Skip lessen in het verleden - die blijven zoals ze zijn
    vandaag = date.today()
    for index_les, les in enumerate(datumprikker.lessen):
        if not les.gaat_door:
            # Behoud lege lesgevers lijst voor "geen les"
            les.lesgevers = []
            continue
        
        if les.datum < vandaag:
            # Behoud bestaande planning voor lessen in het verleden
            continue
            
        les.lesgevers = []
        for index_lesgever, lesgever in enumerate(lesgevers):
            if (index_lesgever, index_les) in assignments and solver.Value(assignments[(index_lesgever, index_les)]):
                les.lesgevers.append(lesgever)
                print(f"Les {les.datetime()} ingevuld met lesgever {lesgever.naam}")
    print("Rooster succesvol ingevuld!")
    return # Geen return waardes


def _make_model(lesgevers: list[Lesgever], datumprikker: DatumPrikker, config: RoosterConfig, hard_min: bool = False) -> tuple[cp_model.CpModel, dict]:   
    model = cp_model.CpModel()
    objective_terms = []
    lessen = datumprikker.lessen # gebruik alleen de lessen in de datumprikker

    # Identificeer lessen die niet doorgaan ("Geen les")
    # Set van index_les die overgeslagen moeten worden
    geen_les_indices = set()
    for index_les, les in enumerate(lessen):
        if not les.gaat_door:
            geen_les_indices.add(index_les)
            print(f"Les {les.datetime()} gaat niet door (overgeslagen in scheduler)")
    
    # Identificeer lessen die al zijn geweest (in het verleden)
    # Deze laten we ongemoeid, ongeacht of ze ingevuld zijn of niet
    vandaag = date.today()
    verleden_les_indices = set()
    for index_les, les in enumerate(lessen):
        if les.datum < vandaag:
            verleden_les_indices.add(index_les)
            print(f"Les {les.datetime()} is al geweest (behouden zoals het is)")
    
    # Combineer indices die we moeten overslaan in de scheduler
    skip_les_indices = geen_les_indices | verleden_les_indices
    
    # Identificeer pre-assigned lesgevers (al ingevuld in de geïmporteerde planning)
    # Set van (index_lesgever, index_les) tuples die al vast staan
    pre_assigned = set()
    for index_les, les in enumerate(lessen):
        if les.lesgevers:  # Als er al lesgevers zijn toegewezen
            for lesgever in les.lesgevers:
                # Vind de index van deze lesgever in de lesgevers lijst met fuzzy matching
                distances = [distance(lesgever.naam, lg.naam) for lg in lesgevers]
                min_distance = min(distances) if distances else float('inf')
                
                if min_distance < 3:
                    index_lesgever = distances.index(min_distance)
                    pre_assigned.add((index_lesgever, index_les))
                    if min_distance > 0:
                        print(f"Pre-assigned: {lesgever.naam} aan {les.datetime()} (gematcht met {lesgevers[index_lesgever].naam})")
                    else:
                        print(f"Pre-assigned: {lesgever.naam} aan {les.datetime()}")
                else:
                    print(f"Waarschuwing: Pre-assigned lesgever '{lesgever.naam}' niet gevonden in beschikbaarheid matrix (beste match afstand: {min_distance})")

    # Maak assignment variabel matrix (en extra data structures voor gemak)
    assignments = {}
    assignments_per_les = [[] for _ in range(len(lessen))]
    assignments_per_lesgever = [[] for _ in range(len(lesgevers))]

    # Harde Constraint: Alleen bij Ja of Misschien kan een lesgever worden ingedeeld
    # Maar: pre-assigned lesgevers worden altijd toegelaten (zelfs als ze Nee hebben of niet in de lijst staan)
    # Skip lessen die niet doorgaan (gaat_door == False) en lessen in het verleden
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):
            # Skip lessen die we niet willen schedulen
            if index_les in skip_les_indices:
                continue
                
            is_pre_assigned = (index_lesgever, index_les) in pre_assigned
            is_available = datumprikker.beschikbaarheid[index_lesgever][index_les] in ["Ja","Misschien"]
            
            if is_available or is_pre_assigned:
                var = model.NewBoolVar(f"assignment_{index_lesgever}_{index_les}")
                assignments[(index_lesgever, index_les)] = var
                assignments_per_les[index_les].append(var)
                assignments_per_lesgever[index_lesgever].append(var)
                
                # Harde constraint: pre-assigned lesgevers MOETEN toegewezen worden
                if is_pre_assigned:
                    model.Add(var == 1)

    # Harde Constraint: Maximum Aantal lesgevers per les (skip lessen die niet doorgaan en verleden)
    for index_les in range(len(lessen)):
        if index_les in skip_les_indices:
            continue
        model.Add(sum(assignments_per_les[index_les]) <= config.lesgever_maximum)

    # Hard of Soft Constraint: Tekort aan lesgevers (skip lessen die niet doorgaan en verleden)
    for index_les in range(len(lessen)):
        if index_les in skip_les_indices:
            continue
        if hard_min:
                model.Add(sum(assignments_per_les[index_les]) >= config.lesgever_minimum)
        else:        
            aantal_tekort = model.NewIntVar(0, config.lesgever_minimum, f"aantal_tekort_{index_les}")
            aantal_lesgevers = sum(assignments_per_les[index_les])
            model.Add(aantal_tekort >= config.lesgever_minimum - aantal_lesgevers)
            model.Add(aantal_tekort >= 0)        
            objective_terms.append(config.penalty_lesgever_tekort * aantal_tekort)

    # Soft: Liever meer lesgevers (maar niet voor pre-assigned, die zijn verplicht)
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):
            if (index_lesgever, index_les) in assignments:
                # Alleen bonus toekennen voor niet-pre-assigned assignments
                if (index_lesgever, index_les) not in pre_assigned:
                    objective_terms.append(-config.lesgever_bonus * assignments[(index_lesgever, index_les)])

    # Soft Constraint: Pentalty per lesgever met Misschien (maar niet voor pre-assigned)
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):
            # Check if assignment variable exists (will not exist for "geen les" lessons)
            if (index_lesgever, index_les) in assignments:
                is_pre_assigned = (index_lesgever, index_les) in pre_assigned
                if not is_pre_assigned and datumprikker.beschikbaarheid[index_lesgever][index_les] == "Misschien":
                    objective_terms.append(config.penalty_misschien * assignments[(index_lesgever, index_les)])


    # Soft Constraint: Pentalty per lesgever zonder ervaring (skip lessen die niet doorgaan en verleden)
    for index_les in range(len(lessen)):
        if index_les in skip_les_indices:
            continue
            
        # Check of er al een ervaren lesgever pre-assigned is
        heeft_al_ervaren_lesgever = any(
            (index_lesgever, index_les) in pre_assigned and lesgevers[index_lesgever].ervaring_jaren >= 1
            for index_lesgever in range(len(lesgevers))
        )
        
        # Als er al een ervaren lesgever is toegewezen, hoeft er geen penalty te zijn
        if not heeft_al_ervaren_lesgever:
            # Check alle ervaren lesgevers die mogelijk aan deze les kunnen worden toegewezen
            ervaren_lesgevers = []
            for index_lesgever in range(len(lesgevers)):
                if (index_lesgever, index_les) in assignments and lesgevers[index_lesgever].ervaring_jaren >= 1:
                    ervaren_lesgevers.append(assignments[(index_lesgever, index_les)])
            
            if ervaren_lesgevers:
                # Create a penalty variable that is 1 if no experienced teacher is assigned
                geen_ervaring_penalty = model.NewBoolVar(f"geen_ervaring_{index_les}")
                model.Add(geen_ervaring_penalty >= 1 - sum(ervaren_lesgevers))
                objective_terms.append(config.penalty_geen_ervaren_lesgever * geen_ervaring_penalty)

    # Soft Constraint: Pentalty per meerdere lessen per week voor dezelfde lesgever
    for index_lesgever in range(len(lesgevers)):
        # Groep weeknummers (skip lessen die niet doorgaan en verleden)
        weeks = {}
        for index_les in range(len(lessen)):
            if index_les in skip_les_indices:
                continue
            week_number = str(lessen[index_les].datum.isocalendar()[:2]) # jaar en week
            if week_number not in weeks:
                weeks[week_number] = []
            if (index_lesgever, index_les) in assignments:
                weeks[week_number].append(assignments[(index_lesgever, index_les)])     

        # Penalty voor elke les meer dan de eerste in de week
        for week_number, week_assignments in weeks.items():
            if len(week_assignments) > 1:
                # Create a penalty variable for extra lessons beyond the first in this week
                extra_lessen_in_week = model.NewIntVar(0, len(week_assignments) - 1, f"extra_lessen_week_{week_number}_{index_lesgever}")
                aantal_lessen_in_week = sum(week_assignments)
                model.Add(extra_lessen_in_week >= aantal_lessen_in_week - 1)
                model.Add(extra_lessen_in_week >= 0)
                objective_terms.append(config.penalty_meerdere_lessen_per_week * extra_lessen_in_week)

    # Soft Constraint: Nonlinear workload distribution penalty using piecewise linear approximation
    if len(lesgevers) > 0 and len(lessen) > 0:
        # Calculate baseline: based on config.richtlijn_lessen_per_week and number of weeks
        # Only count lessons that actually happen (gaat_door == True and not in the past)
        all_weeks = set((les.datum.isocalendar()[0], les.datum.isocalendar()[1]) 
                        for idx, les in enumerate(lessen) if idx not in skip_les_indices)
        aantal_weken = len(all_weeks) if all_weeks else 1
        baseline_int = int(np.round(config.richtlijn_lessen_per_week * aantal_weken))
        baseline_per_lesgever = max(1, baseline_int)
    
        # Apply penalty for each assignment above baseline (quadratic growth via cumulative effect)
        for index_lesgever in range(len(lesgevers)):
            lesgever_total = sum(assignments_per_lesgever[index_lesgever])
            
            # Apply penalty for each level above baseline
            for excess_level in range(len(config.penalty_verdeling_stappen)):
                exceeds_level = model.NewBoolVar(f"exceeds_{index_lesgever}_{excess_level}")
                threshold = baseline_per_lesgever + excess_level + 1
                model.Add(lesgever_total >= threshold).OnlyEnforceIf(exceeds_level)
                model.Add(lesgever_total <= threshold - 1).OnlyEnforceIf(exceeds_level.Not())
                
                penalty = config.penalty_boven_richtlijn * config.penalty_verdeling_stappen[excess_level]
                objective_terms.append(penalty * exceeds_level)

            # Apply penalty for each level below baseline (mirror of above)
            for deficit_level in range(len(config.penalty_verdeling_stappen)):
                threshold = baseline_per_lesgever - deficit_level - 1
                if threshold < 0:
                    break
                below_level = model.NewBoolVar(f"below_{index_lesgever}_{deficit_level}")
                model.Add(lesgever_total <= threshold).OnlyEnforceIf(below_level)
                model.Add(lesgever_total >= threshold + 1).OnlyEnforceIf(below_level.Not())
                
                penalty = config.penalty_onder_richtlijn * config.penalty_verdeling_stappen[deficit_level]
                objective_terms.append(penalty * below_level)

    
    # Solve
    model.Minimize(sum(objective_terms))

    return model, assignments