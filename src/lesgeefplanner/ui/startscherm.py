"""Eerste scherm: nieuw project, doorrollen naar een nieuw jaar, oude YAML/Excel-opzet
importeren, een bestaand bestand openen, of een recent bestand kiezen."""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Callable

from nicegui import events, ui

from ..domain.jaarwissel import rol_project_door
from ..exchange.legacy_import import importeer_oude_opzet
from ..store.document import Document
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
            ui.label("Nieuw jaar op basis van vorig bestand").classes("text-subtitle1")
            ui.label(
                "Rooster en lesgevers (+1 jaar ervaring) blijven; toewijzingen en "
                "beschikbaarheid worden leeggemaakt en de kalender schuift 52 weken op. "
                "Gebruik daarna 'Kalender bijwerken' om de lessen te genereren."
            ).classes("text-caption text-grey-7")
            vorig_pad_veld = ui.input("Pad naar vorig .lesplan-bestand").classes("full-width")
            nieuwe_naam_veld = ui.input(
                "Naam nieuw project", value="Lesgeefplanning " + _volgend_seizoensjaar()
            ).classes("full-width")
            with ui.row().classes("q-mt-sm q-gutter-sm"):
                if native_beschikbaar():
                    ui.button(
                        "Bladeren…", icon="folder_open",
                        on_click=lambda: _bladeren(vorig_pad_veld),
                    ).props("outline")
                ui.button(
                    "Doorrollen naar nieuw jaar", icon="fast_forward",
                    on_click=lambda: _rol_door(vorig_pad_veld.value, nieuwe_naam_veld.value, on_klaar),
                ).props("color=primary")

        with ui.card().classes("q-pa-md q-mt-md").style("width: 480px;"):
            ui.label("Importeer oude opzet (YAML)").classes("text-subtitle1")
            ui.label(
                "Voor wie nog een planning.yml heeft van vóór deze versie. Lesgevers.xlsx "
                "en planning.xlsx zijn optioneel en vullen lesgevers/toewijzingen aan."
            ).classes("text-caption text-grey-7")
            tijdelijke_paden: dict[str, str] = {}
            ui.upload(
                label="planning.yml",
                auto_upload=True,
                on_upload=lambda e: _sla_tijdelijk_op(tijdelijke_paden, "yaml", e),
            ).props('accept=".yml,.yaml" flat dense bordered').classes("full-width q-mt-xs")
            ui.upload(
                label="lesgevers.xlsx (optioneel)",
                auto_upload=True,
                on_upload=lambda e: _sla_tijdelijk_op(tijdelijke_paden, "lesgevers", e),
            ).props('accept=".xlsx" flat dense bordered').classes("full-width q-mt-xs")
            ui.upload(
                label="planning.xlsx (optioneel)",
                auto_upload=True,
                on_upload=lambda e: _sla_tijdelijk_op(tijdelijke_paden, "planning", e),
            ).props('accept=".xlsx" flat dense bordered').classes("full-width q-mt-xs")
            ui.button(
                "Importeren", icon="upload_file",
                on_click=lambda: _klik_importeer_legacy(tijdelijke_paden, on_klaar),
            ).props("color=primary dense").classes("q-mt-sm")

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


def _rol_door(pad_str: str, nieuwe_naam: str, on_klaar: Callable[[], None]) -> None:
    if not pad_str.strip():
        ui.notify("Kies eerst het vorige bestand.", type="warning")
        return
    if not nieuwe_naam.strip():
        ui.notify("Geef het nieuwe project een naam.", type="warning")
        return
    pad = Path(pad_str.strip())
    if not pad.exists():
        ui.notify(f"Bestand niet gevonden: {pad}", type="negative")
        return
    try:
        vorig_doc = Document.open(pad)
        nieuw_project = rol_project_door(vorig_doc.project, nieuwe_naam.strip())
    except Exception as e:
        ui.notify(f"Kon niet doorrollen: {e}", type="negative")
        return
    state.stel_project_in(nieuw_project)
    ui.notify(
        f"{len(nieuw_project.seizoenen)} seizoen(en) en {len(nieuw_project.lesgevers)} "
        f"lesgevers overgenomen. Gebruik 'Kalender bijwerken' om de lessen te genereren.",
        type="positive", multi_line=True,
    )
    on_klaar()


async def _sla_tijdelijk_op(
    paden: dict[str, str], sleutel: str, e: events.UploadEventArguments
) -> None:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(e.file.name).suffix)
    tmp.close()
    await e.file.save(tmp.name)
    paden[sleutel] = tmp.name
    ui.notify(f"{e.file.name} klaar om te importeren.", type="info")


def _klik_importeer_legacy(paden: dict[str, str], on_klaar: Callable[[], None]) -> None:
    if "yaml" not in paden:
        ui.notify("Upload eerst een planning.yml.", type="warning")
        return
    try:
        project, waarschuwingen = importeer_oude_opzet(
            paden["yaml"],
            lesgevers_xlsx=paden.get("lesgevers"),
            planning_xlsx=paden.get("planning"),
        )
    except Exception as e:
        ui.notify(f"Import mislukt: {e}", type="negative")
        return
    finally:
        for pad_str in paden.values():
            Path(pad_str).unlink(missing_ok=True)

    state.stel_project_in(project)
    for waarschuwing in waarschuwingen:
        ui.notify(waarschuwing, type="warning", multi_line=True)
    ui.notify(
        f"Geïmporteerd: {len(project.lessen)} lessen, {len(project.lesgevers)} lesgevers.",
        type="positive",
    )
    on_klaar()
