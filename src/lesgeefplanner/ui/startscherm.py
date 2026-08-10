"""Eerste scherm: een vertrouwd "welkomscherm"-patroon (VS Code/JetBrains/Office) --
recent geopende bestanden prominent en meteen zichtbaar (dat is voor een terugkerende
gebruiker verreweg de meest voorkomende actie), "Nieuw project"/"Bestand openen" als
duidelijke primaire acties ernaast, en de zeldzame/eenmalige acties (jaarwissel, oude YAML
importeren) opgevouwen achter "Meer opties" zodat ze niet met de hoofdstroom concurreren."""
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
    with ui.column().classes("items-center justify-center full-width").style(
        "min-height: 100vh; padding: 32px; gap: 0;"
    ):
        ui.label("Lesgeefplanner").classes("text-h4 q-mb-lg")

        with ui.row().classes("items-start justify-center q-gutter-lg").style(
            "max-width: 900px; width: 100%; flex-wrap: wrap;"
        ):
            _recent_kolom(on_klaar)
            _acties_kolom(on_klaar)


def _recent_kolom(on_klaar: Callable[[], None]) -> None:
    with ui.card().classes("q-pa-md").style("flex: 3 1 380px; min-width: 320px;"):
        ui.label("Recent geopend").classes("text-subtitle1 q-mb-sm")
        recente = laad_recente_bestanden()
        if not recente:
            ui.label(
                "Nog geen projecten geopend. Maak hiernaast een nieuw project aan, of "
                "open een bestaand .lesplan-bestand."
            ).classes("text-caption text-grey-6")
        for pad_str in recente:
            _recent_rij(pad_str, on_klaar)


def _recent_rij(pad_str: str, on_klaar: Callable[[], None]) -> None:
    pad = Path(pad_str)
    with ui.row().classes("items-center cursor-pointer full-width list-item").style(
        "padding: 10px 12px; gap: 10px;"
    ).props("tabindex=0").on(
        "click", lambda: _open_project(pad_str, on_klaar)
    ).on("keydown.enter", lambda: _open_project(pad_str, on_klaar)):
        ui.icon("description").classes("text-grey-7")
        with ui.column().style("gap: 0; min-width: 0; flex: 1;"):
            ui.label(pad.name).classes("text-body2").style(
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
            )
            ui.label(str(pad.parent)).classes("text-caption text-grey-6").style(
                "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
            )


def _acties_kolom(on_klaar: Callable[[], None]) -> None:
    with ui.card().classes("q-pa-md").style("flex: 2 1 300px; min-width: 280px;"):
        ui.label("Aan de slag").classes("text-subtitle1 q-mb-sm")

        naam_veld = ui.input(
            "Naam nieuw project", value="Lesgeefplanning " + _volgend_seizoensjaar()
        ).classes("full-width")
        ui.button(
            "Nieuw project", icon="add",
            on_click=lambda: _nieuw_project(naam_veld.value, on_klaar),
        ).props("color=primary no-caps").classes("full-width q-mt-xs")

        if native_beschikbaar():
            ui.button(
                "Bestand openen...", icon="folder_open",
                on_click=lambda: _bladeren_en_open(on_klaar),
            ).props("outline no-caps").classes("full-width q-mt-sm")
        else:
            pad_veld = ui.input("Pad naar .lesplan-bestand").classes("full-width q-mt-sm")
            ui.button(
                "Openen", icon="folder_open",
                on_click=lambda: _open_project(pad_veld.value, on_klaar),
            ).props("outline no-caps").classes("full-width q-mt-xs")

        with ui.expansion("Meer opties", icon="more_horiz").classes("full-width q-mt-md"):
            _jaarwissel_sectie(on_klaar)
            ui.separator().classes("q-my-sm")
            _legacy_import_sectie(on_klaar)


def _jaarwissel_sectie(on_klaar: Callable[[], None]) -> None:
    ui.label("Nieuw jaar op basis van vorig bestand").classes("text-caption text-weight-bold")
    ui.label(
        "Rooster en lesgevers (+1 jaar ervaring) blijven; indelingen en beschikbaarheid "
        "worden leeggemaakt en de kalender schuift 52 weken op. Gebruik daarna 'Kalender "
        "bijwerken' om de lessen te genereren."
    ).classes("text-caption text-grey-7")
    vorig_pad_veld = ui.input("Pad naar vorig .lesplan-bestand").classes("full-width q-mt-xs")
    nieuwe_naam_veld = ui.input(
        "Naam nieuw project", value="Lesgeefplanning " + _volgend_seizoensjaar()
    ).classes("full-width")
    with ui.row().classes("q-mt-xs q-gutter-sm"):
        if native_beschikbaar():
            ui.button(
                "Bladeren...", icon="folder_open",
                on_click=lambda: _bladeren(vorig_pad_veld),
            ).props("outline dense no-caps")
        ui.button(
            "Doorrollen naar nieuw jaar", icon="fast_forward",
            on_click=lambda: _rol_door(vorig_pad_veld.value, nieuwe_naam_veld.value, on_klaar),
        ).props("color=primary dense no-caps")


def _legacy_import_sectie(on_klaar: Callable[[], None]) -> None:
    ui.label("Importeer oude opzet (YAML)").classes("text-caption text-weight-bold")
    ui.label(
        "Voor wie nog een planning.yml heeft van vóór deze versie. Lesgevers.xlsx en "
        "planning.xlsx zijn optioneel en vullen lesgevers/indelingen aan."
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
    ).props("color=primary dense no-caps").classes("q-mt-sm")


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


async def _bladeren_en_open(on_klaar: Callable[[], None]) -> None:
    """Kiezen EN openen in één stap (i.p.v. eerst bladeren, dan nog een keer 'Openen'
    klikken) -- native bestandskeuze impliceert al dat je dat bestand wilt openen."""
    pad = await kies_bestand_openen(bestandstypes=(("Lesgeefplanning", "*.lesplan"),))
    if pad is None:
        return
    _open_project(str(pad), on_klaar)


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
        f"{len(nieuw_project.seizoenen)} lessenreeks(en) en {len(nieuw_project.lesgevers)} "
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
