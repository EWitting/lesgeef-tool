import ortools.sat.python.cp_model as cp_model
import numpy as np
from .config import RoosterConfig
from .models import Les, Lesgever, Planning, DatumPrikker

def schedule_lessons(datumprikker: DatumPrikker, config: RoosterConfig) -> None:
    """Optimaliseert rooster op basis van een aantal constraints, 
    vooral soft constraints, om rekening te houden met situaties waar een perfect rooster niet gemaakt kan worden.
    Gebruikt Google OR-Tools. Vult alleen de lessen in die in de datumprikker voorkomen.
    
    Harde Constraints:
    - Alleen bij Ja of Misschien kan een lesgever worden ingedeeld (harde constraint)
    - Maximum aantal lesgevers per les (harde constraint)
    
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
    for index_les, les in enumerate(datumprikker.lessen):
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

    # Maak assignment variabel matrix (en extra data structures voor gemak)
    assignments = {}
    assignments_per_les = [[] for _ in range(len(lessen))]
    assignments_per_lesgever = [[] for _ in range(len(lesgevers))]

    # Harde Constraint: Alleen bij Ja of Misschien kan een lesgever worden ingedeeld
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):            
            if datumprikker.beschikbaarheid[index_lesgever][index_les] in ["Ja","Misschien"]: 
                var = model.NewBoolVar(f"assignment_{index_lesgever}_{index_les}")
                assignments[(index_lesgever, index_les)] = var
                assignments_per_les[index_les].append(var)
                assignments_per_lesgever[index_lesgever].append(var)

    # Harde Constraint: Maximum Aantal lesgevers per les
    for index_les in range(len(lessen)):
        model.Add(sum(assignments_per_les[index_les]) <= config.lesgever_maximum)

    # Hard of Soft Constraint: Tekort aan lesgevers
    for index_les in range(len(lessen)):
        if hard_min:
                model.Add(sum(assignments_per_les[index_les]) >= config.lesgever_minimum)
        else:        
            aantal_tekort = model.NewIntVar(0, config.lesgever_minimum, f"aantal_tekort_{index_les}")
            aantal_lesgevers = sum(assignments_per_les[index_les])
            model.Add(aantal_tekort >= config.lesgever_minimum - aantal_lesgevers)
            model.Add(aantal_tekort >= 0)        
            objective_terms.append(config.penalty_lesgever_tekort * aantal_tekort)

    # Soft: Liever meer lesgevers
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):
            if (index_lesgever, index_les) in assignments:
                objective_terms.append(-config.lesgever_bonus * assignments[(index_lesgever, index_les)])

    # Soft Constraint: Pentalty per lesgever met Misschien
    for index_lesgever in range(len(lesgevers)):
        for index_les in range(len(lessen)):
            if datumprikker.beschikbaarheid[index_lesgever][index_les] == "Misschien":
                objective_terms.append(config.penalty_misschien * assignments[(index_lesgever, index_les)])


    # Soft Constraint: Pentalty per lesgever zonder ervaring
    for index_les in range(len(lessen)):
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
        # Groep weeknummers
        weeks = {}
        for index_les in range(len(lessen)):
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
        all_weeks = set((les.datum.isocalendar()[0], les.datum.isocalendar()[1]) for les in lessen)
        aantal_weken = len(all_weeks) if all_weeks else 1
        baseline_int = int(np.round(config.richtlijn_lessen_per_week * aantal_weken))
        baseline_per_lesgever = max(1, baseline_int)
    
        # Apply penalty for each assignment above baseline (quadratic growth via cumulative effect)
        for index_lesgever in range(len(lesgevers)):
            lesgever_total = sum(assignments_per_lesgever[index_lesgever])
            
            # Apply penalty for each level above baseline
            for excess_level in range(len(config.penalty_verdeling_stappen)):
                # Binary indicator: exceeds_level == 1  <=>  lesgever_total >= baseline + excess_level
                exceeds_level = model.NewBoolVar(f"exceeds_{index_lesgever}_{excess_level}")
                threshold = baseline_per_lesgever + excess_level + 1
                model.Add(lesgever_total >= threshold).OnlyEnforceIf(exceeds_level)
                model.Add(lesgever_total <= threshold - 1).OnlyEnforceIf(exceeds_level.Not())
                
                penalty = config.penalty_boven_richtlijn * config.penalty_verdeling_stappen[excess_level]
                objective_terms.append(penalty * exceeds_level)

    
    # Solve
    model.Minimize(sum(objective_terms))

    return model, assignments