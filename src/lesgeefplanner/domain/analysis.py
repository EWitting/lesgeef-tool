"""Analyseert een project en levert bevindingen op. Vervangt het platte-tekstrapport van de
oude src/report.py door gestructureerde, klikbare data. Zie docs/DESIGN.md §5.

Snelheid: geen geneste lussen over lessen x lesgevers x rondes. Bouw eerst lookup-dicts,
loop daarna. Bij ~150 lessen en ~25 lesgevers moet dit ruim onder de 50ms blijven."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..model.entities import Les, Seizoen, les_seizoen_id
from ..model.project import Project
from ..model.scope import Scope
from .beschikbaarheid import verzamel_beschikbaarheid
from .formatting import format_datum
from .werkverdeling import doel_voor_seizoen, lessen_per_seizoen, totaal_voor_lesgever

Ernst = Literal["fout", "waarschuwing", "info"]


class Bevinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    ernst: Ernst
    titel: str
    uitleg: str
    les_id: str | None = None
    lesgever_id: str | None = None
    waarde: float | None = None


def analyseer(project: Project, scope: Scope, peildatum: date) -> list[Bevinding]:
    """Bevindingen over de gegeven scope. Sommige checks (werkverdeling, weekconflicten)
    kijken naar het hele seizoen -- net als de solver (docs/DESIGN.md §4.2) telt "hoeveel
    heeft iemand al gehad" mee, ook als dat buiten de zichtbare scope valt."""
    lessen_in_scope = [
        les for les in project.lessen if les.status == "gaat_door" and scope.bevat(les, peildatum)
    ]
    lessen_in_scope_ids = {les.id for les in lessen_in_scope}
    seizoenen_in_scope = {les_seizoen_id(les) for les in lessen_in_scope}

    lesgever_by_id = {lg.id: lg for lg in project.lesgevers}
    beschikbaarheid = verzamel_beschikbaarheid(project)

    les_ids_in_rondes: set[str] = set()
    for ronde in project.rondes:
        for vraag in ronde.vragen:
            les_ids_in_rondes.add(vraag.les_id)

    bevindingen: list[Bevinding] = []
    bevindingen.extend(
        _analyseer_lessen(lessen_in_scope, lesgever_by_id, beschikbaarheid, les_ids_in_rondes, project.solver_config)
    )
    bevindingen.extend(_analyseer_week_conflicten(project, lessen_in_scope_ids))
    bevindingen.extend(_analyseer_werkverdeling(project, seizoenen_in_scope))
    bevindingen.extend(_analyseer_reacties(project, lessen_in_scope_ids))
    bevindingen.extend(_analyseer_seizoenen_overlap(project.seizoenen))
    bevindingen.extend(_analyseer_les_buiten_seizoen(lessen_in_scope))
    return bevindingen


def _analyseer_lessen(
    lessen: list[Les], lesgever_by_id: dict, beschikbaarheid: dict, les_ids_in_rondes: set[str], config
) -> list[Bevinding]:
    resultaat: list[Bevinding] = []
    for les in lessen:
        if not les.toewijzingen:
            resultaat.append(
                Bevinding(
                    code="les_niet_ingevuld", ernst="fout",
                    titel=f"{format_datum(les.datum)}: niet ingevuld",
                    uitleg="Deze les heeft nog geen enkele lesgever.",
                    les_id=les.id,
                )
            )
        elif len(les.toewijzingen) < config.lesgever_minimum:
            resultaat.append(
                Bevinding(
                    code="les_te_weinig_lesgevers", ernst="fout",
                    titel=f"{format_datum(les.datum)}: te weinig lesgevers "
                    f"({len(les.toewijzingen)}/{config.lesgever_minimum})",
                    uitleg=f"Minimaal {config.lesgever_minimum} lesgevers gewenst, "
                    f"nu {len(les.toewijzingen)}.",
                    les_id=les.id,
                )
            )

        if les.toewijzingen and not any(
            lesgever_by_id[tw.lesgever_id].ervaren
            for tw in les.toewijzingen
            if tw.lesgever_id in lesgever_by_id
        ):
            resultaat.append(
                Bevinding(
                    code="les_geen_ervaren_lesgever", ernst="waarschuwing",
                    titel=f"{format_datum(les.datum)}: geen ervaren lesgever",
                    uitleg="Niemand met minstens 1 jaar ervaring is ingedeeld.",
                    les_id=les.id,
                )
            )

        for tw in les.toewijzingen:
            waarde = beschikbaarheid.get((tw.lesgever_id, les.id))
            naam = lesgever_by_id[tw.lesgever_id].naam if tw.lesgever_id in lesgever_by_id else "Onbekend"
            if waarde == "misschien":
                resultaat.append(
                    Bevinding(
                        code="les_misschien_gebruikt", ernst="waarschuwing",
                        titel=f"{format_datum(les.datum)}: {naam} antwoordde 'misschien'",
                        uitleg=f"{naam} staat ingedeeld maar had 'misschien' geantwoord.",
                        les_id=les.id, lesgever_id=tw.lesgever_id,
                    )
                )
            elif waarde == "nee":
                resultaat.append(
                    Bevinding(
                        code="lesgever_ingedeeld_maar_nee", ernst="fout",
                        titel=f"{format_datum(les.datum)}: {naam} kan niet",
                        uitleg=f"{naam} staat ingedeeld maar antwoordde 'nee' op de "
                        f"beschikbaarheidsronde.",
                        les_id=les.id, lesgever_id=tw.lesgever_id,
                    )
                )

        if les.id not in les_ids_in_rondes:
            resultaat.append(
                Bevinding(
                    code="les_zonder_beschikbaarheid", ernst="waarschuwing",
                    titel=f"{format_datum(les.datum)}: geen beschikbaarheidsronde",
                    uitleg="Deze les zit in geen enkele beschikbaarheidsronde -- er is dus "
                    "niet gevraagd wie kan.",
                    les_id=les.id,
                )
            )
    return resultaat


def _analyseer_week_conflicten(project: Project, lessen_in_scope_ids: set[str]) -> list[Bevinding]:
    per_lesgever_week: dict[tuple[str, tuple[int, int]], list[Les]] = {}
    for les in project.lessen:
        if les.status != "gaat_door":
            continue
        week = les.datum.isocalendar()[:2]
        for tw in les.toewijzingen:
            per_lesgever_week.setdefault((tw.lesgever_id, week), []).append(les)

    lesgever_by_id = {lg.id: lg for lg in project.lesgevers}
    resultaat: list[Bevinding] = []
    for (lesgever_id, _week), lessen in per_lesgever_week.items():
        if len(lessen) < 2:
            continue
        relevante_lessen = [les for les in lessen if les.id in lessen_in_scope_ids]
        if not relevante_lessen:
            continue
        naam = lesgever_by_id[lesgever_id].naam if lesgever_id in lesgever_by_id else "Onbekend"
        datums = ", ".join(format_datum(les.datum) for les in sorted(lessen, key=lambda l: l.datum))
        for les in relevante_lessen:
            resultaat.append(
                Bevinding(
                    code="lesgever_dubbel_in_week", ernst="waarschuwing",
                    titel=f"{naam}: meerdere lessen in dezelfde week",
                    uitleg=f"{naam} staat op {len(lessen)} lessen in dezelfde week: {datums}.",
                    les_id=les.id, lesgever_id=lesgever_id,
                )
            )
    return resultaat


def _analyseer_werkverdeling(project: Project, seizoenen_in_scope: set) -> list[Bevinding]:
    resultaat: list[Bevinding] = []
    per_seizoen = lessen_per_seizoen(project)
    lesgevers = [lg for lg in project.lesgevers if lg.actief]

    for seizoen_sleutel in seizoenen_in_scope:
        lessen = per_seizoen.get(seizoen_sleutel, [])
        doel = doel_voor_seizoen(project, lessen)

        for lg in lesgevers:
            totaal = totaal_voor_lesgever(lg.id, lessen)
            if totaal > doel:
                resultaat.append(
                    Bevinding(
                        code="lesgever_boven_richtlijn", ernst="waarschuwing",
                        titel=f"{lg.naam}: boven de richtlijn ({totaal}/{doel})",
                        uitleg=f"{lg.naam} staat op {totaal} lessen deze lessenreeks, "
                        f"de richtlijn is {doel}.",
                        lesgever_id=lg.id, waarde=float(totaal),
                    )
                )
            elif totaal < doel:
                resultaat.append(
                    Bevinding(
                        code="lesgever_onder_richtlijn", ernst="info",
                        titel=f"{lg.naam}: onder de richtlijn ({totaal}/{doel})",
                        uitleg=f"{lg.naam} staat op {totaal} lessen deze lessenreeks, "
                        f"de richtlijn is {doel}.",
                        lesgever_id=lg.id, waarde=float(totaal),
                    )
                )
    return resultaat


def _analyseer_reacties(project: Project, lessen_in_scope_ids: set[str]) -> list[Bevinding]:
    resultaat: list[Bevinding] = []
    lesgevers_actief = [lg for lg in project.lesgevers if lg.actief]
    for ronde in project.rondes:
        les_ids_ronde = {vraag.les_id for vraag in ronde.vragen}
        if not les_ids_ronde & lessen_in_scope_ids:
            continue
        gereageerd = {antwoord.lesgever_id for antwoord in ronde.antwoorden}
        for lg in lesgevers_actief:
            if lg.id not in gereageerd:
                resultaat.append(
                    Bevinding(
                        code="lesgever_niet_gereageerd", ernst="info",
                        titel=f"{lg.naam}: nog niet gereageerd op '{ronde.naam}'",
                        uitleg=f"{lg.naam} heeft de beschikbaarheidsronde '{ronde.naam}' "
                        f"nog niet ingevuld.",
                        lesgever_id=lg.id,
                    )
                )
    return resultaat


def _analyseer_seizoenen_overlap(seizoenen: list[Seizoen]) -> list[Bevinding]:
    resultaat: list[Bevinding] = []
    for i, s1 in enumerate(seizoenen):
        for s2 in seizoenen[i + 1 :]:
            if s1.begin <= s2.eind and s2.begin <= s1.eind:
                resultaat.append(
                    Bevinding(
                        code="seizoenen_overlappen", ernst="waarschuwing",
                        titel=f"'{s1.naam}' en '{s2.naam}' overlappen",
                        uitleg=(
                            f"'{s1.naam}' ({format_datum(s1.begin)}–{format_datum(s1.eind)}) "
                            f"en '{s2.naam}' ({format_datum(s2.begin)}–{format_datum(s2.eind)}) "
                            f"overlappen. Lessen op de overlappende data horen bij '{s1.naam}' "
                            f"(de eerste lessenreeks in de lijst)."
                        ),
                    )
                )
    return resultaat


def _analyseer_les_buiten_seizoen(lessen: list[Les]) -> list[Bevinding]:
    resultaat: list[Bevinding] = []
    for les in lessen:
        if les_seizoen_id(les) is None:
            resultaat.append(
                Bevinding(
                    code="les_buiten_seizoen", ernst="info",
                    titel=f"{format_datum(les.datum)}: geen lessenreeks",
                    uitleg="Deze les hoort bij geen enkele lessenreeks (normaal voor een "
                    "extra les zonder vaste lessenreeks).",
                    les_id=les.id,
                )
            )
    return resultaat
