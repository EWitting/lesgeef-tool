"""Beschikbaarheidsrondes: aanmaken, het Google Forms-script tonen, antwoorden importeren,
en het responsoverzicht. Zie docs/DESIGN.md §4.5 en docs/PLAN.md fase 6."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from nicegui import events, ui

from ...domain.formatting import format_datum_lang
from ...exchange.forms_import import lees_forms_export
from ...exchange.forms_script import genereer_apps_script, genereer_labellijst
from ...exchange.types import ImportResultaat
from ...model import Ronde
from .. import rondebewerkingen as rb
from ..state import state
from ..velden import bestand_upload
from .scope_balk import create_scope_balk


def create_rondes_paneel(container: ui.column) -> None:
    container.clear()
    if state.doc is None:
        with container:
            ui.label("Geen project geopend.").classes("text-grey-6")
        return

    with container:
        ui.label("Beschikbaarheidsrondes").classes("text-subtitle1 q-mb-xs")
        _nieuwe_ronde_sectie(container)
        ui.separator().classes("q-my-sm")

        project = state.doc.project
        if not project.rondes:
            ui.label("Nog geen rondes aangemaakt.").classes("text-caption text-grey-6")
        for ronde in sorted(project.rondes, key=lambda r: r.aangemaakt_op, reverse=True):
            _ronde_kaart(container, ronde.id)


def _nieuwe_ronde_sectie(container: ui.column) -> None:
    with ui.card().classes("q-pa-sm full-width"):
        ui.label("Nieuwe ronde").classes("text-caption text-weight-bold")
        naam_veld = ui.input("Naam (bv. 'Voorseizoen 1')").classes("full-width")
        ui.label("Voor welke lessen?").classes("text-caption text-grey-7 q-mt-xs")
        # Dezelfde scope-widget als boven de planning (middenpaneel) en dus ook dezelfde
        # onderliggende Scope (docs/DESIGN.md §2.4) -- hier instellen werkt dus meteen door
        # naar 'Automatisch invullen' en het gezondheidspaneel, en andersom.
        scope_rij = ui.row().classes("q-gutter-sm items-center full-width").style(
            "flex-wrap: wrap;"
        )
        create_scope_balk(scope_rij)
        ui.button(
            "Ronde aanmaken",
            on_click=lambda: _klik_ronde_aanmaken(container, naam_veld),
        ).props("color=primary dense no-caps q-mt-xs")


def _klik_ronde_aanmaken(container: ui.column, naam_veld: ui.input) -> None:
    naam = naam_veld.value.strip() if naam_veld.value else ""
    if not naam:
        ui.notify("Geef de ronde een naam.", type="warning")
        return
    ronde_id = rb.maak_ronde(naam, state.scope, state.peildatum())
    ronde = _vind_ronde(ronde_id)
    if ronde is not None and not ronde.vragen:
        ui.notify(
            "Deze ronde heeft geen enkele les geraakt -- controleer 'Voor welke lessen?' "
            "hierboven.",
            type="warning",
        )
    else:
        ui.notify(f"Ronde '{naam}' aangemaakt ({len(ronde.vragen)} lessen).", type="positive")
    create_rondes_paneel(container)
    state.meld_wijziging()


def _vind_ronde(ronde_id: str) -> Ronde | None:
    assert state.doc is not None
    return next((r for r in state.doc.project.rondes if r.id == ronde_id), None)


def _ronde_kaart(container: ui.column, ronde_id: str) -> None:
    ronde = _vind_ronde(ronde_id)
    if ronde is None:
        return
    project = state.doc.project  # type: ignore[union-attr]

    gereageerd_ids = {a.lesgever_id for a in ronde.antwoorden}
    actieve_lesgevers = [lg for lg in project.lesgevers if lg.actief]
    nog_te_vullen = [lg for lg in actieve_lesgevers if lg.id not in gereageerd_ids]

    with ui.expansion(
        f"{ronde.naam} — {len(ronde.vragen)} lessen, "
        f"{len(gereageerd_ids)}/{len(actieve_lesgevers)} gereageerd"
    ).classes("full-width q-mt-xs"):
        ui.label(f"Aangemaakt: {format_datum_lang(ronde.aangemaakt_op.date())}").classes(
            "text-caption text-grey-7"
        )

        with ui.tabs().props("dense no-caps") as tabs:
            tab_formulier = ui.tab("Formulier maken")
            tab_import = ui.tab("Antwoorden importeren")
            tab_overzicht = ui.tab("Overzicht")

        with ui.tab_panels(tabs, value=tab_formulier).classes("full-width"):
            with ui.tab_panel(tab_formulier):
                _formulier_sectie(ronde)
            with ui.tab_panel(tab_import):
                _import_sectie(container, ronde)
            with ui.tab_panel(tab_overzicht):
                _overzicht_sectie(ronde, actieve_lesgevers, nog_te_vullen)


def _formulier_sectie(ronde: Ronde) -> None:
    assert state.doc is not None
    lesgevers = state.doc.project.lesgevers

    ui.label(
        "1. Ga naar script.google.com en maak een nieuw project. "
        "2. Plak onderstaand script (vervang de bestaande inhoud). "
        "3. Klik 'Uitvoeren' en kies de functie 'maakFormulier'. "
        "4. Bekijk het log (Weergave → Logs) voor de link naar het formulier."
    ).classes("text-caption q-mb-xs")

    script = genereer_apps_script(ronde, lesgevers)
    ui.code(script, language="javascript").classes("full-width").style(
        "max-height: 240px; overflow-y: auto;"
    )
    ui.button(
        "Kopieer script", icon="content_copy",
        on_click=lambda: _kopieer(script, "Script gekopieerd."),
    ).props("flat dense")

    with ui.expansion("Handmatig alternatief").classes("full-width q-mt-sm"):
        ui.label(
            "Maak zelf een formulier met een meerkeuzevraag 'Ja/Misschien/Nee' per regel "
            "hieronder, en een 'Wie ben je?'-vraag met deze namen als opties. Laat de "
            "'#nummer' aan het eind van elke vraagtitel staan."
        ).classes("text-caption")
        labels = genereer_labellijst(ronde)
        ui.code(labels, language="text").classes("full-width").style(
            "max-height: 160px; overflow-y: auto;"
        )
        ui.button(
            "Kopieer lijst", icon="content_copy",
            on_click=lambda: _kopieer(labels, "Lijst gekopieerd."),
        ).props("flat dense")


def _kopieer(tekst: str, melding: str) -> None:
    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(tekst)})")
    ui.notify(melding, type="positive")


def _import_sectie(container: ui.column, ronde: Ronde) -> None:
    ui.label(
        "Exporteer het antwoordenbestand via Google Forms → Reacties → xlsx exporteren."
    ).classes("text-caption q-mb-xs")
    bestand_upload(
        "Antwoorden .xlsx", ".xlsx,.xls", lambda e: _klik_upload(container, ronde.id, e),
    )


async def _klik_upload(container: ui.column, ronde_id: str, e: events.UploadEventArguments) -> None:
    assert state.doc is not None
    try:
        data = await e.file.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(data)
        tmp.close()
        ronde = _vind_ronde(ronde_id)
        if ronde is None:
            return
        resultaat = lees_forms_export(Path(tmp.name), ronde, state.doc.project)
        Path(tmp.name).unlink(missing_ok=True)
    except Exception as ex:
        ui.notify(f"Kon bestand niet lezen: {ex}", type="negative")
        return

    for waarschuwing in resultaat.waarschuwingen:
        ui.notify(waarschuwing, type="warning", multi_line=True)

    if resultaat.niet_gekoppelde_kolommen:
        with ui.dialog() as info_dialoog, ui.card():
            ui.label("Niet-gekoppelde kolommen").classes("text-subtitle1")
            for k in resultaat.niet_gekoppelde_kolommen:
                ui.label(f"- {k}").classes("text-caption")
            ui.button("Ok", on_click=info_dialoog.close).props("flat no-caps")
        info_dialoog.open()

    keuzes: dict[str, str | None] = {}
    if resultaat.naamproblemen:
        keuzes = await _toon_naamresolutie(resultaat)
        if keuzes is None:
            ui.notify("Import geannuleerd.", type="info")
            return

    aantal = rb.verwerk_importresultaat(resultaat, keuzes)
    ui.notify(f"{aantal} antwoorden verwerkt.", type="positive")
    create_rondes_paneel(container)
    state.meld_wijziging()


async def _toon_naamresolutie(resultaat: ImportResultaat) -> dict[str, str | None] | None:
    """Toont per onopgeloste naam een keuzelijst met suggesties. Geeft None terug bij
    annuleren, anders ruwe_naam -> gekozen lesgever_id (of None om over te slaan)."""
    assert state.doc is not None
    lesgever_by_id = {lg.id: lg for lg in state.doc.project.lesgevers}
    selects: dict[str, ui.select] = {}

    with ui.dialog() as dialoog, ui.card().style("min-width: 420px;"):
        ui.label(
            f"{len(resultaat.naamproblemen)} naam/namen niet automatisch herkend"
        ).classes("text-subtitle1")
        for probleem in resultaat.naamproblemen:
            opties = {"": "Overslaan"}
            for lesgever_id, score in probleem.voorstellen[:5]:
                naam = lesgever_by_id.get(lesgever_id)
                if naam is not None:
                    opties[lesgever_id] = f"{naam.naam} ({score:.0%})"
            selects[probleem.ruwe_naam] = ui.select(
                opties, label=probleem.ruwe_naam, value=""
            ).classes("full-width")
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat no-caps")
            ui.button(
                "Doorgaan",
                on_click=lambda: dialoog.submit(
                    {naam: (select.value or None) for naam, select in selects.items()}
                ),
            ).props("color=primary no-caps")

    return await dialoog


def _overzicht_sectie(ronde: Ronde, actieve_lesgevers, nog_te_vullen) -> None:
    if not nog_te_vullen:
        ui.label("Iedereen heeft gereageerd.").classes("text-positive text-caption")
    else:
        ui.label(f"Nog te vullen ({len(nog_te_vullen)}):").classes(
            "text-caption text-weight-bold"
        )
        for lg in nog_te_vullen:
            ui.label(f"- {lg.naam}").classes("text-caption")
        herinnering = "\n".join(lg.naam for lg in nog_te_vullen)
        ui.button(
            "Kopieer lijst voor herinnering", icon="content_copy",
            on_click=lambda: _kopieer(herinnering, "Lijst gekopieerd."),
        ).props("flat dense")
