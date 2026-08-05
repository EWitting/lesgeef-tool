"""De solver zelf. Poort van het oude src/schedule.py (origin/ui), met dezelfde getunede
penalty-formules -- die blijven ongewijzigd. Drie inhoudelijke wijzigingen (docs/DESIGN.md
§4.2):

1. Weekconflicten tellen lessen buiten de scope (context, incl. verleden) mee.
2. Werkverdeling telt reeds gegeven lessen mee, per seizoen afzonderlijk berekend.
3. Wijzigingskosten: het weghalen van een bestaande, niet-vaste toewijzing kost een penalty,
   zodat een her-run geen bestaand rooster onnodig omgooit.

De solver muteert niets -- hij krijgt een PlanRequest en geeft een PlanResult terug. De
aanroeper (UI) zet dat om in een voorstel-diff die de gebruiker moet bevestigen."""
from __future__ import annotations

import time as time_module

from ortools.sat.python import cp_model

from ..domain.werkverdeling import bereken_doel
from ..model.entities import les_seizoen_id
from .request import PlanRequest
from .result import PlanResult
from .terms import TermCollector


def los_op(request: PlanRequest) -> PlanResult:
    start = time_module.monotonic()

    model, assignments, termen = _maak_model(request, hard_min=True)
    solver, status = _solve(model, request)
    minimum_afgedwongen = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    if not minimum_afgedwongen:
        model, assignments, termen = _maak_model(request, hard_min=False)
        solver, status = _solve(model, request)

    rekentijd = time_module.monotonic() - start

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return PlanResult(
            status="onhaalbaar", minimum_afgedwongen=False, rekentijd=rekentijd
        )

    toewijzingen: dict[str, list[str]] = {les.id: [] for les in request.lessen_in_scope}
    for (lesgever_id, les_id), var in assignments.items():
        if solver.Value(var):
            toewijzingen[les_id].append(lesgever_id)

    verdeling = termen.breakdown(solver)
    return PlanResult(
        status="optimaal" if status == cp_model.OPTIMAL else "haalbaar",
        minimum_afgedwongen=minimum_afgedwongen,
        toewijzingen=toewijzingen,
        score=sum(verdeling.values()),
        verdeling=verdeling,
        per_les=termen.per_les(solver),
        rekentijd=rekentijd,
    )


def _solve(model: cp_model.CpModel, request: PlanRequest) -> tuple[cp_model.CpSolver, int]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.config.max_rekentijd_seconden
    # Determinisme is hier belangrijker dan snelheid: twee keer draaien op dezelfde data
    # moet exact hetzelfde rooster geven, anders lijkt de app onbetrouwbaar.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    return solver, status


def _maak_model(
    request: PlanRequest, hard_min: bool
) -> tuple[cp_model.CpModel, dict[tuple[str, str], cp_model.IntVar], TermCollector]:
    model = cp_model.CpModel()
    termen = TermCollector()
    config = request.config
    lessen = request.lessen_in_scope
    lesgevers = request.lesgevers
    lesgever_by_id = {lg.id: lg for lg in lesgevers}

    assignments: dict[tuple[str, str], cp_model.IntVar] = {}
    assignments_per_les: dict[str, list] = {les.id: [] for les in lessen}
    assignments_per_lesgever: dict[str, list] = {lg.id: [] for lg in lesgevers}

    vaste_ids_per_les: dict[str, set[str]] = {
        les.id: {tw.lesgever_id for tw in les.toewijzingen if tw.vast} for les in lessen
    }

    for les in lessen:
        vaste_ids = vaste_ids_per_les[les.id]
        for lg in lesgevers:
            waarde = request.beschikbaarheid.get((lg.id, les.id))
            is_vast = lg.id in vaste_ids
            is_beschikbaar = waarde in ("ja", "misschien")
            if not (is_vast or is_beschikbaar):
                continue
            var = model.NewBoolVar(f"x_{lg.id}_{les.id}")
            assignments[(lg.id, les.id)] = var
            assignments_per_les[les.id].append(var)
            assignments_per_lesgever[lg.id].append(var)
            if is_vast:
                model.Add(var == 1)

    # Harde constraint: maximum aantal lesgevers per les
    for les in lessen:
        model.Add(sum(assignments_per_les[les.id]) <= config.lesgever_maximum)

    # Hard of soft: minimum aantal lesgevers per les
    for les in lessen:
        vars_ = assignments_per_les[les.id]
        if hard_min:
            model.Add(sum(vars_) >= config.lesgever_minimum)
        else:
            tekort = model.NewIntVar(0, config.lesgever_minimum, f"tekort_{les.id}")
            model.Add(tekort >= config.lesgever_minimum - sum(vars_))
            model.Add(tekort >= 0)
            termen.add("tekort", config.penalty_lesgever_tekort, tekort, les_id=les.id)

    # Soft: liever meer lesgevers dan het minimum -- bewust alleen de lesgevers BOVEN het
    # minimum verdienen bonus (vaste toewijzingen tellen niet mee, die zijn al verplicht).
    # BUG (tot hier gefixed): eerder kreeg élke niet-vaste toewijzing de volle bonus, ook de
    # toewijzing(en) die alleen het minimum vulden -- bij lesgever_minimum=1 gaf dat bv.
    # -1 bonus per les zelfs als er maar precies 1 (verplichte) lesgever op stond, in
    # plaats van 0. `extra` is dus max(0, aantal niet-vaste toewijzingen - wat daarvan nog
    # nodig is om het minimum te halen), via AddMaxEquality zodat het nooit negatief kan
    # worden (bv. bij een noodgedwongen tekort in de hard_min=False-poging).
    for les in lessen:
        vaste_ids = vaste_ids_per_les[les.id]
        niet_vaste_vars = [
            assignments[(lg.id, les.id)] for lg in lesgevers
            if (lg.id, les.id) in assignments and lg.id not in vaste_ids
        ]
        if not niet_vaste_vars:
            continue
        resterend_minimum = max(0, config.lesgever_minimum - len(vaste_ids))
        werkelijk_extra = model.NewIntVar(
            -resterend_minimum, len(niet_vaste_vars) - resterend_minimum,
            f"werkelijk_extra_{les.id}",
        )
        model.Add(werkelijk_extra == sum(niet_vaste_vars) - resterend_minimum)
        extra = model.NewIntVar(0, len(niet_vaste_vars), f"extra_{les.id}")
        model.AddMaxEquality(extra, [werkelijk_extra, model.NewConstant(0)])
        termen.add("bezetting_bonus", -config.lesgever_bonus, extra, les_id=les.id)

    # Soft: penalty per lesgever met "misschien" (niet voor vaste toewijzingen)
    for les in lessen:
        vaste_ids = vaste_ids_per_les[les.id]
        for lg in lesgevers:
            key = (lg.id, les.id)
            if key not in assignments or lg.id in vaste_ids:
                continue
            if request.beschikbaarheid.get(key) == "misschien":
                termen.add(
                    "misschien", config.penalty_misschien, assignments[key],
                    les_id=les.id, lesgever_id=lg.id,
                )

    # Soft: penalty als geen ervaren lesgever is ingedeeld
    for les in lessen:
        heeft_al_ervaren_vast = any(
            lesgever_by_id[lg_id].ervaren
            for lg_id in vaste_ids_per_les[les.id]
            if lg_id in lesgever_by_id
        )
        if heeft_al_ervaren_vast:
            continue
        ervaren_vars = [
            assignments[(lg.id, les.id)]
            for lg in lesgevers
            if lg.ervaren and (lg.id, les.id) in assignments
        ]
        if ervaren_vars:
            geen_ervaring = model.NewBoolVar(f"geen_ervaring_{les.id}")
            model.Add(geen_ervaring >= 1 - sum(ervaren_vars))
            termen.add(
                "geen_ervaren", config.penalty_geen_ervaren_lesgever, geen_ervaring,
                les_id=les.id,
            )

    _voeg_week_conflict_termen_toe(model, termen, request, assignments, config)
    _voeg_werkverdeling_termen_toe(model, termen, request, assignments, config)
    _voeg_wijzigingskosten_toe(termen, request, assignments, config)

    model.Minimize(sum(termen.objective_terms()))
    return model, assignments, termen


def _voeg_week_conflict_termen_toe(
    model: cp_model.CpModel,
    termen: TermCollector,
    request: PlanRequest,
    assignments: dict[tuple[str, str], cp_model.IntVar],
    config,
) -> None:
    """Penalty voor meerdere lessen per week voor dezelfde lesgever. Telt lessen buiten de
    scope (context, incl. verleden) mee als een vast aantal -- als iemand zaterdag al
    vaststaat (context), moet zondag in dezelfde week nog steeds pijn doen."""
    context_per_week: dict[str, dict[tuple[int, int], int]] = {}
    for les in request.lessen_context:
        week = les.datum.isocalendar()[:2]
        for tw in les.toewijzingen:
            per_lg = context_per_week.setdefault(tw.lesgever_id, {})
            per_lg[week] = per_lg.get(week, 0) + 1

    scope_vars_per_week: dict[str, dict[tuple[int, int], list]] = {}
    for les in request.lessen_in_scope:
        week = les.datum.isocalendar()[:2]
        for lg in request.lesgevers:
            key = (lg.id, les.id)
            if key in assignments:
                per_lg = scope_vars_per_week.setdefault(lg.id, {})
                per_lg.setdefault(week, []).append(assignments[key])

    for lg in request.lesgevers:
        weken = set(scope_vars_per_week.get(lg.id, {})) | set(context_per_week.get(lg.id, {}))
        for week in weken:
            scope_vars = scope_vars_per_week.get(lg.id, {}).get(week, [])
            if not scope_vars:
                continue  # solver kan hier toch niets aan veranderen
            vast_aantal = context_per_week.get(lg.id, {}).get(week, 0)
            bovengrens = vast_aantal + len(scope_vars)
            extra = model.NewIntVar(0, bovengrens, f"week_extra_{lg.id}_{week}")
            totaal = vast_aantal + sum(scope_vars)
            model.Add(extra >= totaal - 1)
            model.Add(extra >= 0)
            termen.add(
                "week_conflict", config.penalty_meerdere_lessen_per_week, extra,
                lesgever_id=lg.id,
            )


def _voeg_werkverdeling_termen_toe(
    model: cp_model.CpModel,
    termen: TermCollector,
    request: PlanRequest,
    assignments: dict[tuple[str, str], cp_model.IntVar],
    config,
) -> None:
    """Nonlineaire werkverdeling-penalty, per seizoen afzonderlijk (nooit gemengd). Telt
    lessen die al gegeven zijn (context) mee in het totaal -- dit is de fix voor de TODO
    'rekening houden met ervaring/belasting tijdens het seizoen' uit de oude planner."""
    scope_per_seizoen: dict[str | None, list] = {}
    for les in request.lessen_in_scope:
        scope_per_seizoen.setdefault(les_seizoen_id(les), []).append(les)

    context_per_seizoen: dict[str | None, list] = {}
    for les in request.lessen_context:
        context_per_seizoen.setdefault(les_seizoen_id(les), []).append(les)

    for seizoen_sleutel in set(scope_per_seizoen) | set(context_per_seizoen):
        scope_lessen = scope_per_seizoen.get(seizoen_sleutel, [])
        context_lessen = context_per_seizoen.get(seizoen_sleutel, [])

        alle_weken = {les.datum.isocalendar()[:2] for les in scope_lessen + context_lessen}
        aantal_weken = len(alle_weken) if alle_weken else 1
        doel = bereken_doel(config.richtlijn_lessen_per_week, aantal_weken)

        for lg in request.lesgevers:
            scope_vars = [
                assignments[(lg.id, les.id)]
                for les in scope_lessen
                if (lg.id, les.id) in assignments
            ]
            if not scope_vars:
                continue  # solver kan het totaal van deze lesgever dit seizoen niet wijzigen

            reeds = sum(
                1
                for les in context_lessen
                for tw in les.toewijzingen
                if tw.lesgever_id == lg.id
            )
            totaal = reeds + sum(scope_vars)
            bovengrens = reeds + len(scope_vars)

            for niveau in range(len(config.penalty_verdeling_stappen)):
                drempel = doel + niveau + 1
                if drempel > bovengrens:
                    break
                boven = model.NewBoolVar(f"boven_{lg.id}_{seizoen_sleutel}_{niveau}")
                model.Add(totaal >= drempel).OnlyEnforceIf(boven)
                model.Add(totaal <= drempel - 1).OnlyEnforceIf(boven.Not())
                penalty = config.penalty_boven_richtlijn * config.penalty_verdeling_stappen[niveau]
                termen.add("boven_richtlijn", penalty, boven, lesgever_id=lg.id)

            for niveau in range(len(config.penalty_verdeling_stappen)):
                drempel = doel - niveau - 1
                if drempel < 0:
                    break
                onder = model.NewBoolVar(f"onder_{lg.id}_{seizoen_sleutel}_{niveau}")
                model.Add(totaal <= drempel).OnlyEnforceIf(onder)
                model.Add(totaal >= drempel + 1).OnlyEnforceIf(onder.Not())
                penalty = config.penalty_onder_richtlijn * config.penalty_verdeling_stappen[niveau]
                termen.add("onder_richtlijn", penalty, onder, lesgever_id=lg.id)


def _voeg_wijzigingskosten_toe(
    termen: TermCollector,
    request: PlanRequest,
    assignments: dict[tuple[str, str], cp_model.IntVar],
    config,
) -> None:
    """Het weghalen van een bestaande, NIET-vaste toewijzing kost een penalty. Iemand
    toevoegen aan een lege plek kost niets; vervangen kost automatisch (weghalen +
    toevoegen)."""
    for les in request.lessen_in_scope:
        for tw in les.toewijzingen:
            if tw.vast:
                continue
            key = (tw.lesgever_id, les.id)
            if key in assignments:
                termen.add(
                    "wijziging", config.penalty_wijziging, 1 - assignments[key],
                    les_id=les.id, lesgever_id=tw.lesgever_id,
                )
