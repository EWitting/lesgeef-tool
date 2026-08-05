"""Dialoog voor een eenmalige extra les (bv. een Open Les), los van de seizoensgebonden
kalender-generatie in jaarplanning.py -- hoort daarom bij "kalender samenstellen" in de
linkerrail in plaats van bij de acties op de zichtbare planning in het middenpaneel."""
from __future__ import annotations

from datetime import date

from nicegui import ui

from ...domain.formatting import format_datum_lang, parse_nl_tijd
from .. import lesbewerkingen as lb
from ..state import state
from ..velden import datum_veld, tijd_veld


async def toon_extra_les_dialoog() -> None:
    if state.doc is None:
        return
    with ui.dialog() as dialoog, ui.card():
        ui.label("Extra les toevoegen").classes("text-subtitle1")
        datum_veld_el = datum_veld("Datum", date.today().isoformat()).classes("full-width")
        with ui.row():
            begin_veld = tijd_veld("Begintijd", "10:00")
            eind_veld = tijd_veld("Eindtijd", "12:00")
        titel_veld = ui.input("Titel (bv. 'Open Les')").classes("full-width")
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat no-caps")
            ui.button(
                "Toevoegen",
                on_click=lambda: dialoog.submit(
                    (datum_veld_el.value, begin_veld.value, eind_veld.value, titel_veld.value)
                ),
            ).props("color=primary no-caps")

    resultaat = await dialoog
    if resultaat is None:
        return
    datum_str, begin_str, eind_str, titel = resultaat
    try:
        datum_waarde = date.fromisoformat(datum_str)
        begin_tijd = parse_nl_tijd(begin_str)
        eind_tijd = parse_nl_tijd(eind_str)
    except ValueError:
        ui.notify(
            "Ongeldige datum of tijd. Gebruik het formaat HH:MM voor tijden.", type="negative",
        )
        return
    lb.voeg_extra_les_toe(datum_waarde, begin_tijd, eind_tijd, titel)
    ui.notify(f"Extra les toegevoegd op {format_datum_lang(datum_waarde)}.", type="positive")
    state.meld_wijziging()
