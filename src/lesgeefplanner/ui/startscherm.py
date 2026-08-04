"""Eerste scherm: nieuw project, bestaand bestand openen, of een recent bestand kiezen.

Legacy-import ('Importeer oude opzet uit YAML/Excel', zie docs/PLAN.md fase 8) hoort hier
straks ook, maar bestaat nog niet -- er wordt bewust geen knop voor getoond die nog niets
doet."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from nicegui import ui

from ..store.instellingen import laad_recente_bestanden
from .bestandsdialoog import kies_bestand_openen, native_beschikbaar
from .state import state


def create_startscherm(on_klaar: Callable[[], None]) -> None:
    with ui.column().classes("items-center q-mt-xl full-width"):
        ui.label("Lesgeefplanner").classes("text-h4 q-mb-md")

        with ui.card().classes("q-pa-md").style("width: 480px;"):
            ui.label("Nieuw project").classes("text-subtitle1")
            naam_veld = ui.input(
                "Naam", value="Lesgeefplanning " + _volgend_seizoensjaar()
            ).classes("full-width")
            ui.button(
                "Nieuw project aanmaken",
                icon="add",
                on_click=lambda: _nieuw_project(naam_veld.value, on_klaar),
            ).props("color=primary").classes("q-mt-sm")

        with ui.card().classes("q-pa-md q-mt-md").style("width: 480px;"):
            ui.label("Bestaand project openen").classes("text-subtitle1")
            pad_veld = ui.input("Pad naar .lesplan-bestand").classes("full-width")
            with ui.row().classes("q-mt-sm q-gutter-sm"):
                if native_beschikbaar():
                    ui.button(
                        "Bladeren…",
                        icon="folder_open",
                        on_click=lambda: _bladeren(pad_veld),
                    ).props("outline")
                ui.button(
                    "Openen",
                    icon="folder_open",
                    on_click=lambda: _open_project(pad_veld.value, on_klaar),
                ).props("color=primary")

        recente = laad_recente_bestanden()
        if recente:
            with ui.card().classes("q-pa-md q-mt-md").style("width: 480px;"):
                ui.label("Recent geopend").classes("text-subtitle1 q-mb-sm")
                for pad_str in recente:
                    ui.button(
                        Path(pad_str).name,
                        icon="history",
                        on_click=lambda p=pad_str: _open_project(p, on_klaar),
                    ).props("flat align=left").classes("full-width").tooltip(pad_str)


def _volgend_seizoensjaar() -> str:
    from datetime import date

    vandaag = date.today()
    # Een lesgeefjaar loopt over de jaarwisseling; vanaf september tellen we het als
    # "dit jaar - volgend jaar".
    if vandaag.month >= 7:
        return f"{vandaag.year}-{vandaag.year + 1}"
    return f"{vandaag.year - 1}-{vandaag.year}"


def _nieuw_project(naam: str, on_klaar: Callable[[], None]) -> None:
    if not naam.strip():
        ui.notify("Geef het project een naam.", type="warning")
        return
    state.nieuw_project(naam.strip())
    on_klaar()


async def _bladeren(pad_veld: ui.input) -> None:
    pad = await kies_bestand_openen(bestandstypes=(("Lesgeefplanning", "*.lesplan"),))
    if pad is not None:
        pad_veld.value = str(pad)


def _open_project(pad_str: str, on_klaar: Callable[[], None]) -> None:
    if not pad_str.strip():
        ui.notify("Kies eerst een bestand.", type="warning")
        return
    pad = Path(pad_str.strip())
    if not pad.exists():
        ui.notify(f"Bestand niet gevonden: {pad}", type="negative")
        return
    try:
        state.open_project(pad)
    except Exception as e:
        ui.notify(f"Kon bestand niet openen: {e}", type="negative")
        return
    on_klaar()
