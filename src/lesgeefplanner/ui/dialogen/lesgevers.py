"""Lesgeverslijst: naam, ervaring, actief. Zie docs/BESLISSINGEN.md fase 6 -- dit vult een
gat dat docs/PLAN.md openliet (het bestand stond al in DESIGN.md §7, maar was aan geen
enkele fase toegewezen)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from nicegui import events, ui

from ...exchange.roster_import import DoelVeld, lees_lesgevers
from .. import lesgeverbewerkingen as lgb
from ..state import state
from ..velden import bestand_upload

_VELD_LABEL: dict[DoelVeld, str] = {
    "naam": "Naam", "ervaring_jaren": "Ervaring (jaren)", "actief": "Actief",
}


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

        with ui.row().classes("q-mt-sm items-center full-width").style(
            "flex-wrap: wrap; gap: 6px;"
        ):
            naam_veld = ui.input("Nieuwe lesgever").props("dense").style(
                "flex: 1 1 140px; min-width: 140px;"
            )
            ui.button(
                icon="add", on_click=lambda: _klik_toevoegen(container, naam_veld)
            ).props("dense color=primary")

        ui.separator().classes("q-my-sm")
        ui.label("Importeren uit Excel").classes("text-caption text-weight-bold")
        ui.label(
            "Bestaande namen worden bijgewerkt (ervaring/actief); nieuwe namen toegevoegd."
        ).classes("text-caption text-grey-7")
        bestand_upload(
            "Lesgevers .xlsx", ".xlsx,.xls", lambda e: _klik_upload(container, e),
        )


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
    with ui.row().classes("items-center full-width").style("flex-wrap: wrap; gap: 6px;"):
        naam_veld = ui.input(value=lg.naam).props("dense").style(
            "flex: 2 1 100px; min-width: 100px;"
        )
        naam_veld.on(
            "blur",
            lambda: (
                lgb.wijzig_lesgever(lesgever_id, naam=naam_veld.value),
                state.meld_wijziging(),
            ),
        )
        ervaring_veld = ui.number(value=lg.ervaring_jaren, min=0, max=50).props(
            "dense"
        ).style("flex: 1 1 60px; min-width: 60px;").tooltip("Ervaring (jaren)")
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


async def _klik_upload(container: ui.column, e: events.UploadEventArguments) -> None:
    data = await e.file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.write(data)
    tmp.close()
    try:
        resultaat = lees_lesgevers(tmp.name)
        if resultaat.kolommapping_nodig:
            mapping = await _toon_kolommapping_dialoog(resultaat.kolommapping_nodig)
            if mapping is None:
                ui.notify("Import geannuleerd.", type="info")
                return
            resultaat = lees_lesgevers(tmp.name, kolommapping=mapping)
    except Exception as ex:
        ui.notify(f"Kon bestand niet lezen: {ex}", type="negative")
        return
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    for waarschuwing in resultaat.waarschuwingen:
        ui.notify(waarschuwing, type="warning")

    aantal = lgb.samenvoeg_geimporteerde_lesgevers(resultaat.lesgevers)
    ui.notify(f"{aantal} lesgevers verwerkt.", type="positive")
    create_lesgevers_paneel(container)
    state.meld_wijziging()


async def _toon_kolommapping_dialoog(
    kolommapping_nodig: dict[DoelVeld, list[str]],
) -> dict[DoelVeld, str] | None:
    selects: dict[DoelVeld, ui.select] = {}
    with ui.dialog() as dialoog, ui.card().style("min-width: 380px;"):
        ui.label("Kolommen koppelen").classes("text-subtitle1")
        ui.label(
            "Deze kolommen konden niet automatisch herkend worden -- kies zelf welke bij "
            "welk veld hoort."
        ).classes("text-caption text-grey-7")
        for veld, kolommen in kolommapping_nodig.items():
            selects[veld] = ui.select(kolommen, label=_VELD_LABEL.get(veld, veld)).classes(
                "full-width"
            )
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat no-caps")

            def _klik_doorgaan() -> None:
                mapping = {veld: select.value for veld, select in selects.items()}
                if any(v is None for v in mapping.values()):
                    ui.notify("Kies voor elk veld een kolom.", type="warning")
                    return
                dialoog.submit(mapping)

            ui.button("Doorgaan", on_click=_klik_doorgaan).props("color=primary no-caps")
    return await dialoog
