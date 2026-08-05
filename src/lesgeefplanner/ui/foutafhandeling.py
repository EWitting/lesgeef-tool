"""Centrale foutafhandeling: onverwachte fouten komen NOOIT als ruwe traceback in de UI.
Details gaan naar een logbestand, de gebruiker krijgt een Nederlandse melding met een
knop om de technische details te kopiëren (voor een bugreport). Zie docs/PLAN.md fase 9.

NiceGUI's standaardgedrag bij een onverwachte fout in een klik-handler is: alleen loggen
naar de server-console (`log.exception`, zie nicegui/app/app.py) -- in de gepakte app heeft
niemand die console, dus zonder dit is een fout voor de gebruiker volledig onzichtbaar
("er gebeurt niets als ik klik")."""
from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from nicegui import app, ui
from platformdirs import user_data_dir

APP_NAAM = "Lesgeefplanner"


def logbestand_pad() -> Path:
    return Path(user_data_dir(APP_NAAM, appauthor=False)) / "log.txt"


def registreer_foutafhandeling() -> None:
    """Eenmalig aan te roepen bij het opstarten van de app (__main__.py)."""
    app.on_exception(_toon_en_log_fout)


def _toon_en_log_fout(exception: Exception) -> None:
    details = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )
    _schrijf_log(details)

    with ui.dialog() as dialoog, ui.card():
        ui.label("Er ging iets mis").classes("text-subtitle1 text-negative")
        ui.label(str(exception) or type(exception).__name__).classes("text-caption")
        ui.label(f"Details zijn opgeslagen in {logbestand_pad()}").classes(
            "text-caption text-grey-7"
        )
        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button(
                "Kopieer technische details", on_click=lambda: _kopieer(details)
            ).props("flat no-caps")
            ui.button("Sluiten", on_click=dialoog.close).props("color=primary no-caps")
    dialoog.open()


def _schrijf_log(details: str) -> None:
    tijdstip = datetime.now().isoformat(timespec="seconds")
    try:
        pad = logbestand_pad()
        pad.parent.mkdir(parents=True, exist_ok=True)
        with pad.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {tijdstip} ===\n{details}\n")
    except OSError:
        pass  # kan het logbestand niet schrijven -- de melding aan de gebruiker gaat wel door


def _kopieer(tekst: str) -> None:
    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(tekst)})")
    ui.notify("Gekopieerd naar klembord.", type="positive")
