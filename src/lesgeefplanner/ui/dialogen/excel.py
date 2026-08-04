"""Excel-export en het terug-importeren van wijzigingen (samenvoeging, geen overschrijving).
Zie docs/DESIGN.md §4.3/§4.4 en docs/PLAN.md fase 7."""
from __future__ import annotations

import tempfile
from datetime import date, time
from pathlib import Path

from nicegui import events, ui
from platformdirs import user_documents_dir

from ...domain.formatting import format_datum, format_tijd
from ...exchange.excel_export import export_planning
from ...exchange.excel_import import lees_sheet
from ...exchange.types import NaamProbleem, Wijziging
from .. import excelbewerkingen as eb
from ..bestandsdialoog import kies_bestand_opslaan, native_beschikbaar
from ..state import state
from .diff_dialoog import DiffRegel, toon_diff_dialoog

_SOORT_LABEL = {
    "toegevoegd": "Lesgever toegevoegd",
    "verwijderd": "Lesgever verwijderd",
    "status": "Status gewijzigd",
    "titel": "Titel gewijzigd",
}


def create_excel_paneel(container: ui.column) -> None:
    container.clear()
    if state.doc is None:
        with container:
            ui.label("Geen project geopend.").classes("text-grey-6")
        return

    with container:
        ui.label("Excel (Google Drive)").classes("text-subtitle1 q-mb-xs")
        ui.label(
            "Exporteer de planning naar Excel om te delen via Google Drive. Wijzigingen "
            "die daar direct in de sheet gemaakt worden, kun je hierna weer terughalen."
        ).classes("text-caption text-grey-7 q-mb-sm")

        laatste_pad = state.doc.project.werkblad.laatste_export_pad
        if laatste_pad:
            ui.label(f"Laatst geëxporteerd naar: {laatste_pad}").classes(
                "text-caption text-grey-7"
            )

        ui.button(
            "Exporteer Excel", icon="download",
            on_click=lambda: _klik_exporteer(container),
        ).props("color=primary dense").classes("q-mb-sm")

        ui.separator().classes("q-my-sm")
        ui.label("Wijzigingen terughalen").classes("text-caption text-weight-bold")
        ui.upload(
            label="Excel-bestand",
            auto_upload=True,
            on_upload=lambda e: _klik_upload(container, e),
        ).props('accept=".xlsx,.xls" flat dense bordered').classes("max-w-xs")


async def _klik_exporteer(container: ui.column) -> None:
    assert state.doc is not None
    standaardnaam = f"{state.doc.project.naam}.xlsx"
    if native_beschikbaar():
        pad = await kies_bestand_opslaan(standaardnaam)
    else:
        pad = await _vraag_pad_via_dialoog(standaardnaam)
    if pad is None:
        return

    try:
        export_planning(state.doc.project, pad)
    except Exception as ex:
        ui.notify(f"Export mislukt: {ex}", type="negative")
        return

    with state.doc.muteer("Excel geëxporteerd"):
        state.doc.project.werkblad.laatste_export_pad = str(pad)
    ui.notify(f"Geëxporteerd naar {pad}", type="positive")
    create_excel_paneel(container)
    state.meld_wijziging()


async def _vraag_pad_via_dialoog(standaardnaam: str) -> Path | None:
    standaardpad = str(Path(user_documents_dir()) / standaardnaam)
    with ui.dialog() as dialoog, ui.card():
        ui.label("Exporteer Excel").classes("text-subtitle1")
        veld = ui.input("Bestandspad", value=standaardpad).classes("full-width").style(
            "width: 420px;"
        )
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
            ui.button(
                "Exporteren", on_click=lambda: dialoog.submit(veld.value)
            ).props("color=primary")
    resultaat = await dialoog
    return Path(resultaat) if resultaat else None


async def _klik_upload(container: ui.column, e: events.UploadEventArguments) -> None:
    assert state.doc is not None
    try:
        data = await e.file.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(data)
        tmp.close()
        wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(tmp.name, state.doc.project)
        Path(tmp.name).unlink(missing_ok=True)
    except Exception as ex:
        ui.notify(f"Kon bestand niet lezen: {ex}", type="negative")
        return

    if niet_gekoppeld:
        with ui.dialog() as info, ui.card():
            ui.label(f"{len(niet_gekoppeld)} rij(en) niet gekoppeld").classes("text-subtitle1")
            for regel in niet_gekoppeld:
                ui.label(f"- {regel}").classes("text-caption")
            ui.label(
                "Deze rijen worden genegeerd. Controleer of de Code-kolom nog intact is."
            ).classes("text-caption text-grey-7 q-mt-xs")
            ui.button("Ok", on_click=info.close).props("flat")
        info.open()

    if naamproblemen:
        keuzes = await _toon_naamresolutie(naamproblemen)
        if keuzes is None:
            ui.notify("Import geannuleerd.", type="info")
            return
        for probleem in naamproblemen:
            gekozen_id = keuzes.get(probleem.ruwe_naam)
            if gekozen_id and probleem.les_id is not None:
                wijzigingen.append(
                    Wijziging(
                        les_id=probleem.les_id, soort="toegevoegd", lesgever_id=gekozen_id,
                        oud="", nieuw=probleem.ruwe_naam, zekerheid="voorstel",
                    )
                )

    if not wijzigingen:
        ui.notify("Geen wijzigingen gevonden.", type="info")
        return

    project = state.doc.project
    regels = [
        DiffRegel(id=str(i), omschrijving=_omschrijving(w, project))
        for i, w in enumerate(wijzigingen)
    ]
    gekozen_regels = await toon_diff_dialoog(
        f"Wijzigingen uit Excel ({len(regels)})", regels, "Toepassen"
    )
    if gekozen_regels is None:
        return

    toe_te_passen = [w for i, w in enumerate(wijzigingen) if str(i) in gekozen_regels]
    aantal = eb.pas_wijzigingen_toe(toe_te_passen)
    ui.notify(f"{aantal} wijzigingen toegepast.", type="positive")
    create_excel_paneel(container)
    state.meld_wijziging()


async def _toon_naamresolutie(naamproblemen: list[NaamProbleem]) -> dict[str, str | None] | None:
    assert state.doc is not None
    lesgever_by_id = {lg.id: lg for lg in state.doc.project.lesgevers}
    selects: dict[str, ui.select] = {}

    with ui.dialog() as dialoog, ui.card().style("min-width: 420px;"):
        ui.label(f"{len(naamproblemen)} naam/namen niet automatisch herkend").classes(
            "text-subtitle1"
        )
        for probleem in naamproblemen:
            opties = {"": "Overslaan"}
            for lesgever_id, score in probleem.voorstellen[:5]:
                lg = lesgever_by_id.get(lesgever_id)
                if lg is not None:
                    opties[lesgever_id] = f"{lg.naam} ({score:.0%})"
            selects[probleem.ruwe_naam] = ui.select(
                opties, label=probleem.ruwe_naam, value=""
            ).classes("full-width")
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
            ui.button(
                "Doorgaan",
                on_click=lambda: dialoog.submit(
                    {naam: (select.value or None) for naam, select in selects.items()}
                ),
            ).props("color=primary")

    return await dialoog


def _omschrijving(w: Wijziging, project) -> str:
    les = next((l for l in project.lessen if l.id == w.les_id), None)
    wanneer = f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)}" if les else "?"
    label = _SOORT_LABEL.get(w.soort, w.soort)
    if w.soort in ("toegevoegd", "verwijderd"):
        naam = w.nieuw or w.oud
        return f"{wanneer}: {label} — {naam}"
    return f"{wanneer}: {label} — '{w.oud}' → '{w.nieuw}'"
