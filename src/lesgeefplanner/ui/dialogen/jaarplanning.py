"""Jaarplanning: seizoenen en het weekrooster, met een live teller en een expliciete
'Kalender bijwerken'-stap. Vervangt de oude planning.yml volledig (docs/PLAN.md fase 8)."""
from __future__ import annotations

from datetime import date

from nicegui import ui

from ...domain.calendar import bereken_kalender_diff, gewenste_lessen, pas_kalender_diff_toe
from ...domain.formatting import DAGEN_NL, format_datum, format_tijd, parse_nl_tijd
from .. import jaarplanningbewerkingen as jpb
from ..state import state
from .diff_dialoog import DiffRegel, toon_diff_dialoog

_DAG_OPTIES = {i: naam.capitalize() for i, naam in enumerate(DAGEN_NL)}


def create_jaarplanning_paneel(container: ui.column) -> None:
    container.clear()
    if state.doc is None:
        with container:
            ui.label("Geen project geopend.").classes("text-grey-6")
        return

    project = state.doc.project

    with container:
        with ui.row().classes("items-center justify-between full-width"):
            ui.label("Jaarplanning").classes("text-subtitle1")
            aantal = len(gewenste_lessen(project))
            ui.label(f"{aantal} lessen bij huidige instellingen").classes(
                "text-caption text-grey-7"
            )

        ui.button(
            "Kalender bijwerken", icon="sync",
            on_click=lambda: _klik_kalender_bijwerken(container),
        ).props("color=primary dense").classes("q-my-sm")
        ui.label(
            "Past niets automatisch toe -- toont eerst wat er zou veranderen."
        ).classes("text-caption text-grey-7")

        ui.separator().classes("q-my-sm")
        ui.label("Seizoenen").classes("text-caption text-weight-bold")
        for seizoen in project.seizoenen:
            _seizoen_rij(container, seizoen.id)
        _nieuw_seizoen_rij(container)

        ui.separator().classes("q-my-sm")
        ui.label("Jaarrooster (standaard weekrooster)").classes("text-caption text-weight-bold")
        ui.label(
            "Wordt gebruikt door elk seizoen zonder eigen weekrooster."
        ).classes("text-caption text-grey-7")
        _weekrooster_editor(container, None, project.weekrooster)

        ui.separator().classes("q-my-sm")
        with ui.expansion("Geavanceerd: project als JSON (alleen-lezen)").classes("full-width"):
            ui.code(project.model_dump_json(indent=2), language="json").classes(
                "full-width"
            ).style("max-height: 300px; overflow-y: auto;")


def _seizoen_rij(container: ui.column, seizoen_id: str) -> None:
    seizoen = _vind_seizoen(seizoen_id)
    if seizoen is None:
        return
    with ui.card().classes("q-pa-sm full-width q-mb-xs"):
        with ui.row().classes("items-center q-gutter-xs no-wrap"):
            naam_veld = ui.input(value=seizoen.naam).props("dense").style("width: 140px;")
            naam_veld.on(
                "blur", lambda: _wijzig(seizoen_id, container, naam=naam_veld.value)
            )
            begin_veld = ui.input(value=seizoen.begin.isoformat(), label="Begin").props(
                "dense"
            ).style("width: 110px;")
            eind_veld = ui.input(value=seizoen.eind.isoformat(), label="Eind").props(
                "dense"
            ).style("width: 110px;")
            begin_veld.on(
                "blur",
                lambda: _wijzig(seizoen_id, container, begin=_parse_datum_of_meld(begin_veld.value)),
            )
            eind_veld.on(
                "blur",
                lambda: _wijzig(seizoen_id, container, eind=_parse_datum_of_meld(eind_veld.value)),
            )
            ui.button(
                icon="delete",
                on_click=lambda: _klik_verwijder_seizoen(container, seizoen_id),
            ).props("flat dense size=sm color=negative")

        eigen = seizoen.weekrooster is not None
        ui.checkbox(
            "Eigen weekrooster (i.p.v. jaarrooster)",
            value=eigen,
            on_change=lambda e: _klik_eigen_weekrooster(container, seizoen_id, e.value),
        )
        if eigen:
            _weekrooster_editor(container, seizoen_id, seizoen.weekrooster)


def _nieuw_seizoen_rij(container: ui.column) -> None:
    with ui.row().classes("items-center q-gutter-xs no-wrap q-mt-xs"):
        naam_veld = ui.input("Naam nieuw seizoen").props("dense").style("width: 160px;")
        begin_veld = ui.input("Begin (JJJJ-MM-DD)").props("dense").style("width: 130px;")
        eind_veld = ui.input("Eind (JJJJ-MM-DD)").props("dense").style("width: 130px;")
        ui.button(
            icon="add",
            on_click=lambda: _klik_nieuw_seizoen(container, naam_veld, begin_veld, eind_veld),
        ).props("dense color=primary")


def _klik_nieuw_seizoen(container, naam_veld, begin_veld, eind_veld) -> None:
    naam = (naam_veld.value or "").strip()
    begin = _parse_datum_of_meld(begin_veld.value)
    eind = _parse_datum_of_meld(eind_veld.value)
    if not naam or begin is None or eind is None:
        ui.notify("Vul naam, begin en eind in (JJJJ-MM-DD).", type="warning")
        return
    if eind < begin:
        ui.notify("Einddatum ligt voor de begindatum.", type="warning")
        return
    jpb.voeg_seizoen_toe(naam, begin, eind)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _klik_verwijder_seizoen(container: ui.column, seizoen_id: str) -> None:
    jpb.verwijder_seizoen(seizoen_id)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _klik_eigen_weekrooster(container: ui.column, seizoen_id: str, actief: bool) -> None:
    jpb.zet_eigen_weekrooster(seizoen_id, actief)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _wijzig(seizoen_id: str, container: ui.column, **kwargs) -> None:
    if any(v is None for v in kwargs.values()):
        ui.notify("Ongeldige datum (gebruik JJJJ-MM-DD).", type="warning")
        return
    jpb.wijzig_seizoen(seizoen_id, **kwargs)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _weekrooster_editor(container: ui.column, seizoen_id: str | None, slots: list) -> None:
    for i, slot in enumerate(slots):
        with ui.row().classes("items-center q-gutter-xs no-wrap"):
            ui.label(_DAG_OPTIES[slot.dag]).classes("text-caption").style("width: 80px;")
            ui.label(f"{format_tijd(slot.begin_tijd)} - {format_tijd(slot.eind_tijd)}").classes(
                "text-caption"
            ).style("width: 110px;")
            ui.button(
                icon="delete",
                on_click=lambda i=i: _klik_verwijder_slot(container, seizoen_id, i),
            ).props("flat dense size=sm color=negative")

    with ui.row().classes("items-center q-gutter-xs no-wrap q-mt-xs"):
        dag_veld = ui.select(_DAG_OPTIES, value=0).props("dense").style("width: 110px;")
        begin_veld = ui.input("Begin", value="16:00").props("dense").style("width: 70px;")
        eind_veld = ui.input("Eind", value="19:00").props("dense").style("width: 70px;")
        ui.button(
            icon="add",
            on_click=lambda: _klik_voeg_slot_toe(
                container, seizoen_id, dag_veld, begin_veld, eind_veld
            ),
        ).props("dense color=primary")


def _klik_voeg_slot_toe(container, seizoen_id, dag_veld, begin_veld, eind_veld) -> None:
    try:
        begin_tijd = parse_nl_tijd(begin_veld.value)
        eind_tijd = parse_nl_tijd(eind_veld.value)
    except ValueError:
        ui.notify("Ongeldige tijd (gebruik HH:MM).", type="warning")
        return
    jpb.voeg_weekslot_toe(seizoen_id, dag_veld.value, begin_tijd, eind_tijd)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _klik_verwijder_slot(container: ui.column, seizoen_id: str | None, index: int) -> None:
    jpb.verwijder_weekslot(seizoen_id, index)
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


async def _klik_kalender_bijwerken(container: ui.column) -> None:
    assert state.doc is not None
    project = state.doc.project
    diff = bereken_kalender_diff(project)
    if diff.is_leeg():
        ui.notify("Kalender is al up-to-date.", type="info")
        return

    regels: list[DiffRegel] = []
    for les in diff.toe_te_voegen:
        regels.append(
            DiffRegel(
                id=les.id, omschrijving=f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)}",
                groep="+ Toe te voegen",
            )
        )
    for les in diff.te_verwijderen:
        regels.append(
            DiffRegel(
                id=les.id, omschrijving=f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)}",
                groep="− Te verwijderen",
            )
        )
    for les, reden in diff.conflicten:
        regels.append(
            DiffRegel(
                id=les.id,
                omschrijving=f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)} ({reden})",
                aangevinkt=False, groep="⚠ Conflicten (heeft werk erin, wordt anders overgeslagen)",
            )
        )
    les_by_id = {l.id: l for l in project.lessen}
    for les_id, nieuwe_eind in diff.tijd_updates:
        les = les_by_id.get(les_id)
        if les is None:
            continue
        regels.append(
            DiffRegel(
                id=les_id,
                omschrijving=f"{format_datum(les.datum)}: eindtijd → {format_tijd(nieuwe_eind)}",
                groep="Tijd aangepast",
            )
        )

    geaccepteerd = await toon_diff_dialoog(
        f"Kalender bijwerken ({len(regels)} wijzigingen)", regels, "Toepassen"
    )
    if geaccepteerd is None:
        return

    with state.doc.muteer("Kalender bijgewerkt"):
        pas_kalender_diff_toe(state.doc.project, diff, geaccepteerd)

    ui.notify(f"{len(geaccepteerd)} wijzigingen toegepast.", type="positive")
    create_jaarplanning_paneel(container)
    state.meld_wijziging()


def _vind_seizoen(seizoen_id: str):
    assert state.doc is not None
    return next((s for s in state.doc.project.seizoenen if s.id == seizoen_id), None)


def _parse_datum_of_meld(tekst: str) -> date | None:
    try:
        return date.fromisoformat(tekst.strip())
    except (ValueError, AttributeError):
        return None
