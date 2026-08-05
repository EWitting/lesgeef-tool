"""Excel-export en het terug-importeren van wijzigingen (samenvoeging, geen overschrijving).
Zie docs/DESIGN.md §4.3/§4.4 en docs/PLAN.md fase 7.

Export en import staan als twee losse knoppen naast elkaar in de header (niet als één
gecombineerde dialoog) -- export is een directe actie (kies pad, klaar), import is zijn
eigen kleine flow (bestand kiezen -> naamresolutie -> diff bevestigen). Ze samenpersen in
één dialoog verstopte de import-knop achter de export-knop."""
from __future__ import annotations

import tempfile
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
from ..velden import bestand_upload
from .diff_dialoog import DiffRegel, toon_diff_dialoog

_SOORT_LABEL = {
    "toegevoegd": "Lesgever toegevoegd",
    "verwijderd": "Lesgever verwijderd",
    "status": "Status gewijzigd",
    "titel": "Titel gewijzigd",
}


async def exporteer_excel() -> None:
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
    state.meld_wijziging()


def open_import_dialoog() -> None:
    assert state.doc is not None
    with ui.dialog() as dialoog, ui.card().style("min-width: 380px; max-width: 460px;"):
        ui.label("Wijzigingen terughalen uit Excel").classes("text-subtitle1 q-mb-xs")
        ui.label(
            "Wijzigingen die rechtstreeks in de geëxporteerde sheet zijn gemaakt (bv. "
            "iemand die zelf zijn naam invult) worden hier samengevoegd -- je krijgt "
            "eerst te zien wat er verandert, niets wordt zomaar overschreven."
        ).classes("text-caption text-grey-7 q-mb-sm")
        bestand_upload("Excel-bestand", ".xlsx,.xls", lambda e: _klik_upload(dialoog, e))
        with ui.row().classes("justify-end full-width q-mt-md"):
            ui.button("Sluiten", on_click=dialoog.close).props("flat no-caps")
    dialoog.open()


async def _vraag_pad_via_dialoog(standaardnaam: str) -> Path | None:
    standaardpad = str(Path(user_documents_dir()) / standaardnaam)
    with ui.dialog() as dialoog, ui.card():
        ui.label("Exporteer Excel").classes("text-subtitle1")
        veld = ui.input("Bestandspad", value=standaardpad).classes("full-width").style(
            "width: 420px;"
        )
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat no-caps")
            ui.button(
                "Exporteren", on_click=lambda: dialoog.submit(veld.value)
            ).props("color=primary no-caps")
    resultaat = await dialoog
    return Path(resultaat) if resultaat else None


async def _klik_upload(dialoog: ui.dialog, e: events.UploadEventArguments) -> None:
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
            ui.button("Ok", on_click=info.close).props("flat no-caps")
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
    dialoog.close()
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
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat no-caps")
            ui.button(
                "Doorgaan",
                on_click=lambda: dialoog.submit(
                    {naam: (select.value or None) for naam, select in selects.items()}
                ),
            ).props("color=primary no-caps")

    return await dialoog


def _omschrijving(w: Wijziging, project) -> str:
    les = next((l for l in project.lessen if l.id == w.les_id), None)
    wanneer = f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)}" if les else "?"
    label = _SOORT_LABEL.get(w.soort, w.soort)
    if w.soort in ("toegevoegd", "verwijderd"):
        naam = w.nieuw or w.oud
        return f"{wanneer}: {label} — {naam}"
    return f"{wanneer}: {label} — '{w.oud}' → '{w.nieuw}'"
