"""Herbruikbare datum-/tijd-invoervelden: een tekstveld (blijft direct leesbaar en
typebaar) met een kalender-/klok-icoon dat een standaard Quasar-picker opent, in plaats
van een kaal tekstveld met een format-hint ("JJJJ-MM-DD") die de gebruiker exact moet
natypen. `label`/`value`/`.style()`/`.on("blur", ...)` werken hetzelfde als een gewone
`ui.input`, want dat is precies wat dit teruggeeft."""
from __future__ import annotations

from typing import Callable

from nicegui import events, ui


def datum_veld(label: str, waarde: str = "") -> ui.input:
    # Eén klik op een dag = een complete, ondubbelzinnige keuze -- de popup sluit dus
    # meteen (geen aparte "Ok" nodig, dat was een overbodige extra klik).
    with ui.input(label, value=waarde).props("dense") as veld:
        with veld.add_slot("append"):
            ui.icon("edit_calendar").classes("cursor-pointer text-grey-7").on(
                "click", lambda: menu.open()
            )
        with ui.menu().props("no-parent-event") as menu:
            # Quasar's QDate-component gebruikt standaard zijn eigen Engelse taalpakket
            # (zondag eerst) -- dat volgt NIET automatisch de taal van Windows, dus zonder
            # deze prop expliciet te zetten blijft het zondag-eerst ongeacht de systeemtaal.
            # "1" = maandag, ongeacht locale.
            ui.date().props(
                'mask=YYYY-MM-DD first-day-of-week="1"'
            ).bind_value(veld).on_value_change(lambda: menu.close())
    return veld


def tijd_veld(label: str, waarde: str = "") -> ui.input:
    # De klok-picker kiest uur en minuut in twee stappen -- automatisch sluiten na de
    # eerste stap zou de minuutkeuze afkappen, dus hier BLIJFT een expliciete "Ok".
    with ui.input(label, value=waarde).props("dense") as veld:
        with veld.add_slot("append"):
            ui.icon("schedule").classes("cursor-pointer text-grey-7").on(
                "click", lambda: menu.open()
            )
        with ui.menu().props("no-parent-event") as menu:
            with ui.time().props("mask=HH:mm format24h").bind_value(veld):
                with ui.row().classes("justify-end full-width"):
                    ui.button("Ok", on_click=menu.close).props("flat dense no-caps")
    return veld


def bestand_upload(
    label: str, accept: str, on_upload: Callable[[events.UploadEventArguments], None],
) -> ui.upload:
    """Quasar's upload-widget heeft standaard een effen blauwe balk als "titel" (niet als
    knop herkenbaar) -- een expliciete "klik om te kiezen"-tekst errboven maakt duidelijk
    dat het een actie is, niet enkel een label."""
    ui.label(f"Sleep {label} hierheen, of klik om te kiezen:").classes(
        "text-caption text-grey-7"
    )
    return ui.upload(
        label=label, auto_upload=True, on_upload=on_upload,
    ).props(f'accept="{accept}" flat dense bordered').classes("full-width")
