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
from .extra_les import toon_extra_les_dialoog
from ..velden import datum_veld, tijd_veld

_DAG_OPTIES = {i: naam.capitalize() for i, naam in enumerate(DAGEN_NL)}


def create_jaarplanning_paneel(container: ui.column) -> None:
    container.clear()
    if state.doc is None:
        with container:
            ui.label("Geen project geopend.").classes("text-grey-6")
        return

    project = state.doc.project

    with container:
        ui.label("Jaarplanning").classes("text-subtitle1")

        # Volgorde volgt de gebruiker: eerst instellen (seizoenen, weekrooster), dan pas de
        # actie die daarvan afhangt (kalender samenstellen) -- niet andersom (zie
        # docs/BESLISSINGEN.md, "jaarplanning-volgorde").
        ui.label("Lessenreeksen").classes("text-caption text-weight-bold q-mt-sm")
        for seizoen in project.seizoenen:
            _seizoen_rij(container, seizoen.id)
        _nieuw_seizoen_rij(container)

        ui.separator().classes("q-my-sm")
        ui.label("Jaarrooster (standaard weekrooster)").classes("text-caption text-weight-bold")
        ui.label(
            "Wordt gebruikt door elke lessenreeks zonder eigen weekrooster."
        ).classes("text-caption text-grey-7")
        _weekrooster_editor(container, None, project.weekrooster)

        ui.separator().classes("q-my-md")
        ui.label("Kalender samenstellen").classes("text-caption text-weight-bold")
        aantal = len(gewenste_lessen(project))
        ui.label(f"{aantal} lessen bij huidige instellingen.").classes(
            "text-caption text-grey-7"
        )
        with ui.row().classes("items-center q-gutter-sm q-mt-xs"):
            ui.button(
                "Kalender bijwerken", icon="sync",
                on_click=lambda: _klik_kalender_bijwerken(container),
            ).props("color=primary dense no-caps")
            ui.button(
                "Extra les toevoegen", icon="add",
                on_click=_klik_extra_les,
            ).props("flat dense color=primary no-caps")
        ui.label(
            "'Kalender bijwerken' past niets automatisch toe -- toont eerst wat er zou "
            "veranderen op basis van lessenreeksen en weekrooster hierboven. 'Extra les "
            "toevoegen' is voor eenmalige, losse lessen (bv. een Open Les)."
        ).classes("text-caption text-grey-7")


async def _klik_extra_les() -> None:
    await toon_extra_les_dialoog()


def _seizoen_rij(container: ui.column, seizoen_id: str) -> None:
    seizoen = _vind_seizoen(seizoen_id)
    if seizoen is None:
        return
    with ui.card().classes("q-pa-sm full-width q-mb-xs"):
        with ui.row().classes("items-center full-width").style(
            "flex-wrap: wrap; gap: 6px;"
        ):
            naam_veld = ui.input(value=seizoen.naam).props("dense").style(
                "flex: 1 1 100px; min-width: 100px;"
            )
            naam_veld.on(
                "blur", lambda: _wijzig(seizoen_id, container, naam=naam_veld.value)
            )
            begin_veld = datum_veld("Begin", seizoen.begin.isoformat()).style(
                "flex: 1 1 110px; min-width: 110px;"
            )
            eind_veld = datum_veld("Eind", seizoen.eind.isoformat()).style(
                "flex: 1 1 110px; min-width: 110px;"
            )
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
    with ui.row().classes("items-center full-width q-mt-xs").style(
        "flex-wrap: wrap; gap: 6px;"
    ):
        naam_veld = ui.input("Naam nieuwe lessenreeks").props("dense").style(
            "flex: 1 1 140px; min-width: 140px;"
        )
        begin_veld = datum_veld("Begin").style("flex: 1 1 130px; min-width: 130px;")
        eind_veld = datum_veld("Eind").style("flex: 1 1 130px; min-width: 130px;")
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
        with ui.row().classes("items-center full-width").style("flex-wrap: wrap; gap: 6px;"):
            ui.label(_DAG_OPTIES[slot.dag]).classes("text-caption").style(
                "flex: 1 1 70px; min-width: 70px;"
            )
            ui.label(f"{format_tijd(slot.begin_tijd)} - {format_tijd(slot.eind_tijd)}").classes(
                "text-caption"
            ).style("flex: 2 1 100px; min-width: 100px;")
            ui.button(
                icon="delete",
                on_click=lambda i=i: _klik_verwijder_slot(container, seizoen_id, i),
            ).props("flat dense size=sm color=negative")

    with ui.row().classes("items-center full-width q-mt-xs").style(
        "flex-wrap: wrap; gap: 6px;"
    ):
        dag_veld = ui.select(_DAG_OPTIES, value=0).props("dense").style(
            "flex: 1 1 100px; min-width: 100px;"
        )
        begin_veld = tijd_veld("Begin", "16:00").style("flex: 1 1 90px; min-width: 90px;")
        eind_veld = tijd_veld("Eind", "19:00").style("flex: 1 1 90px; min-width: 90px;")
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
