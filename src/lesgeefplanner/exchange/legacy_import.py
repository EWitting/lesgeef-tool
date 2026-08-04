"""Eenmalige migratie van de oude YAML/Excel-opzet naar een Project. Zie docs/DESIGN.md
§6.1. Dit wordt precies één keer per team gebruikt, bij de overstap naar deze rewrite --
daarna bestaat de YAML niet meer (docs/PLAN.md fase 8)."""
from __future__ import annotations

from datetime import date, time
from pathlib import Path

import yaml

from ..domain.calendar import bereken_kalender_diff, pas_kalender_diff_toe
from ..domain.names import is_exact, stel_voor
from ..model.entities import Les, Lesgever, Seizoen, Toewijzing, WeekSlot
from ..model.project import Project
from .excel_import import _parse_dag_maand_cel, _parse_tijd_cel
from .roster_import import lees_lesgevers

_DAG_NAAR_NUMMER = {
    "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
    "vrijdag": 4, "zaterdag": 5, "zondag": 6,
}


def importeer_oude_opzet(
    planning_yml: str | Path,
    lesgevers_xlsx: str | Path | None = None,
    planning_xlsx: str | Path | None = None,
) -> tuple[Project, list[str]]:
    """Geeft (project, waarschuwingen) terug. Beschikbaarheid uit oude forms-exports wordt
    BEWUST niet gemigreerd -- te weinig waarde, te veel randgevallen voor een eenmalige
    migratie."""
    waarschuwingen: list[str] = []
    planning_yml = Path(planning_yml)
    with planning_yml.open("r", encoding="utf-8") as f:
        ruw = yaml.safe_load(f) or {}

    project = Project(naam=planning_yml.stem)

    project.weekrooster = [_weekslot(d) for d in ruw.get("weekrooster", [])]

    for ruw_seizoen in ruw.get("seizoenen", []):
        seizoen = Seizoen(
            naam=ruw_seizoen["naam"],
            begin=_parse_datum(ruw_seizoen["begin"]),
            eind=_parse_datum(ruw_seizoen["eind"]),
        )
        if "weekrooster" in ruw_seizoen and ruw_seizoen["weekrooster"] is not None:
            seizoen.weekrooster = [_weekslot(d) for d in ruw_seizoen["weekrooster"]]
        project.seizoenen.append(seizoen)

    # Genereer de reguliere lessen via dezelfde kalenderlogica als de rest van de app
    # (domain/calendar.py), in plaats van de weekiteratie hier te herhalen.
    diff = bereken_kalender_diff(project)
    alle_ids = {les.id for les in diff.toe_te_voegen}
    pas_kalender_diff_toe(project, diff, alle_ids)

    for extra_les in ruw.get("extra-lessen", []):
        for dag in extra_les.get("dagen", []):
            datum = _parse_datum(dag["datum"])
            begin_tijd, eind_tijd = _parse_tijdvak(dag["tijd"])
            seizoen = _vind_seizoen(project.seizoenen, datum)
            project.lessen.append(
                Les(
                    datum=datum, begin_tijd=begin_tijd, eind_tijd=eind_tijd,
                    seizoen_id=seizoen.id if seizoen else None,
                    titel=extra_les["naam"], soort="extra", beschermd=True,
                )
            )

    for activiteit in ruw.get("activiteiten", []):
        datum = _parse_datum(activiteit["datum"])
        gaat_door = activiteit["les-gaat-door"]
        naam = activiteit["naam"]
        tijd_tekst = activiteit.get("tijd")
        treffers = [les for les in project.lessen if les.datum == datum]
        if not treffers:
            waarschuwingen.append(
                f"Activiteit '{naam}' op {datum.isoformat()} hoort bij geen enkele les "
                f"en is overgeslagen."
            )
            continue
        for les in treffers:
            les.titel = naam
            les.beschermd = True
            if not gaat_door:
                les.status = "vervallen"
                les.vervallen_reden = naam
                les.toewijzingen = []
            if tijd_tekst:
                les.begin_tijd, les.eind_tijd = _parse_tijdvak(tijd_tekst)

    if lesgevers_xlsx is not None:
        _importeer_lesgevers(project, lesgevers_xlsx, waarschuwingen)

    if planning_xlsx is not None:
        _importeer_toewijzingen(project, planning_xlsx, waarschuwingen)

    return project, waarschuwingen


def _parse_datum(waarde) -> date:
    if isinstance(waarde, date):
        return waarde
    return date.fromisoformat(str(waarde))


def _parse_tijd(waarde: str) -> time:
    uur, minuut = waarde.strip().split(":")
    return time(int(uur), int(minuut))


def _parse_tijdvak(waarde: str) -> tuple[time, time]:
    begin_tekst, eind_tekst = [d.strip() for d in waarde.split("-")]
    return _parse_tijd(begin_tekst), _parse_tijd(eind_tekst)


def _weekslot(ruw: dict) -> WeekSlot:
    begin_tijd, eind_tijd = _parse_tijdvak(ruw["tijd"])
    return WeekSlot(dag=_DAG_NAAR_NUMMER[ruw["dag"]], begin_tijd=begin_tijd, eind_tijd=eind_tijd)


def _vind_seizoen(seizoenen: list[Seizoen], datum: date) -> Seizoen | None:
    for seizoen in seizoenen:
        if seizoen.begin <= datum <= seizoen.eind:
            return seizoen
    return None


def _importeer_lesgevers(project: Project, pad, waarschuwingen: list[str]) -> None:
    resultaat = lees_lesgevers(pad)
    if resultaat.kolommapping_nodig:
        waarschuwingen.append(
            "Kon lesgevers.xlsx niet automatisch lezen -- kolommen "
            f"{sorted(resultaat.kolommapping_nodig)} niet herkend. Lesgevers zijn niet "
            "geïmporteerd; voeg ze na de migratie handmatig toe of importeer opnieuw."
        )
        return
    project.lesgevers = resultaat.lesgevers
    waarschuwingen.extend(resultaat.waarschuwingen)


def _importeer_toewijzingen(project: Project, pad, waarschuwingen: list[str]) -> None:
    """Koppelt rijen uit de oude planning.xlsx aan de net gegenereerde lessen op
    (dag, maand, begintijd) -- zonder jaar, om dezelfde reden als excel_import.py: de oude
    export schreef de datum als tekst zonder jaartal."""
    import pandas as pd

    try:
        df = pd.read_excel(pad, sheet_name="Planning")
    except Exception as ex:
        waarschuwingen.append(f"Kon planning.xlsx niet lezen: {ex}")
        return

    if "Seizoen" in df.columns:
        df["Seizoen"] = df["Seizoen"].ffill()
    if "Week" in df.columns:
        df["Week"] = df["Week"].ffill()

    kolommen = list(df.columns)
    if "Tijd" not in kolommen or "Info" not in kolommen or "Datum" not in kolommen:
        waarschuwingen.append(
            "planning.xlsx mist de kolommen 'Datum'/'Tijd'/'Info' -- toewijzingen niet "
            "geïmporteerd."
        )
        return
    tijd_idx = kolommen.index("Tijd")
    info_idx = kolommen.index("Info")
    lesgever_kolommen = kolommen[tijd_idx + 1 : info_idx]

    lessen_by_sleutel: dict[tuple[int, int, time], list[Les]] = {}
    for les in project.lessen:
        sleutel = (les.datum.day, les.datum.month, les.begin_tijd)
        lessen_by_sleutel.setdefault(sleutel, []).append(les)

    for _, row in df.iterrows():
        dag_maand = _parse_dag_maand_cel(row.get("Datum"))
        tijd = _parse_tijd_cel(row.get("Tijd"))
        if dag_maand is None or tijd is None:
            continue
        kandidaten = lessen_by_sleutel.get((dag_maand[0], dag_maand[1], tijd), [])
        if len(kandidaten) != 1:
            continue
        les = kandidaten[0]

        namen = [
            str(row[c]).strip() for c in lesgever_kolommen
            if pd.notna(row[c]) and str(row[c]).strip()
        ]
        if any(n.lower().startswith("geen les") for n in namen):
            continue  # al afgehandeld via activiteiten

        for naam in namen:
            lesgever = next((lg for lg in project.lesgevers if lg.naam == naam), None)
            if lesgever is None:
                voorstellen = stel_voor(naam, project.lesgevers)
                if voorstellen and is_exact(voorstellen[0][1]):
                    lesgever = voorstellen[0][0]
                else:
                    waarschuwingen.append(
                        f"'{naam}' in planning.xlsx niet gevonden in de lesgeverslijst "
                        f"-- overgeslagen."
                    )
                    continue
            if not any(tw.lesgever_id == lesgever.id for tw in les.toewijzingen):
                les.toewijzingen.append(
                    Toewijzing(lesgever_id=lesgever.id, vast=True, bron="import")
                )
                les.beschermd = True
