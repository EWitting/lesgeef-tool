"""Lesgeverslijst: naam, ervaring, actief. Zie docs/BESLISSINGEN.md fase 6 -- dit vult een
gat dat docs/PLAN.md openliet (het bestand stond al in DESIGN.md §7, maar was aan geen
enkele fase toegewezen)."""
from __future__ import annotations

from nicegui import ui

from .. import lesgeverbewerkingen as lgb
from ..state import state


def create_lesgevers_paneel(container: ui.column) -> None:
    container.clear()
    if state.doc is None:
        with container:
            ui.label("Geen project geopend.").classes("text-grey-6")
        return

    with container:
        ui.label("Lesgevers").classes("text-subtitle1 q-mb-xs")
        lesgevers = sorted(state.doc.project.lesgevers, key=lambda l: l.naam.lower())
        if not lesgevers:
            ui.label("Nog geen lesgevers.").classes("text-caption text-grey-6")
        for lg in lesgevers:
            _lesgever_rij(container, lg.id)

        with ui.row().classes("q-mt-sm q-gutter-xs items-center"):
            naam_veld = ui.input("Nieuwe lesgever").props("dense").style("width: 160px;")
            ui.button(
                icon="add", on_click=lambda: _klik_toevoegen(container, naam_veld)
            ).props("dense color=primary")


def _klik_toevoegen(container: ui.column, naam_veld: ui.input) -> None:
    naam = (naam_veld.value or "").strip()
    if not naam:
        ui.notify("Geef een naam op.", type="warning")
        return
    lgb.voeg_lesgever_toe(naam)
    create_lesgevers_paneel(container)
    state.meld_wijziging()


def _lesgever_rij(container: ui.column, lesgever_id: str) -> None:
    lg = _vind(lesgever_id)
    if lg is None:
        return
    with ui.row().classes("items-center q-gutter-xs full-width no-wrap"):
        naam_veld = ui.input(value=lg.naam).props("dense").style("width: 110px;")
        naam_veld.on(
            "blur",
            lambda: (
                lgb.wijzig_lesgever(lesgever_id, naam=naam_veld.value),
                state.meld_wijziging(),
            ),
        )
        ervaring_veld = ui.number(value=lg.ervaring_jaren, min=0, max=50).props(
            "dense"
        ).style("width: 60px;").tooltip("Ervaring (jaren)")
        ervaring_veld.on(
            "blur",
            lambda: (
                lgb.wijzig_lesgever(lesgever_id, ervaring_jaren=int(ervaring_veld.value or 0)),
                state.meld_wijziging(),
            ),
        )
        ui.checkbox(
            value=lg.actief,
            on_change=lambda e: (
                lgb.wijzig_lesgever(lesgever_id, actief=e.value),
                state.meld_wijziging(),
            ),
        ).tooltip("Actief")
        ui.button(
            icon="delete", on_click=lambda: _klik_verwijderen(container, lesgever_id)
        ).props("flat dense size=sm color=negative")


def _klik_verwijderen(container: ui.column, lesgever_id: str) -> None:
    lgb.verwijder_lesgever(lesgever_id)
    create_lesgevers_paneel(container)
    state.meld_wijziging()


def _vind(lesgever_id: str):
    assert state.doc is not None
    return next((l for l in state.doc.project.lesgevers if l.id == lesgever_id), None)
