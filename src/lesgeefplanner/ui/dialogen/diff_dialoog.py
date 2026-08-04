"""Herbruikbare bevestigingsdialoog voor voorstellen die de gebruiker per regel moet
goed- of afkeuren: kalender-hergeneratie (fase 8), solvervoorstel (fase 4), en straks
Excel-samenvoeging (fase 7). Zie docs/DESIGN.md §7: "Bouw het één keer."

Vorm is altijd hetzelfde: een lijst met regels, een vinkje per regel, knoppen
Toepassen/Annuleren. `toon_diff_dialoog()` geeft de set aangevinkte regel-ids terug (of
None bij annuleren); de aanroeper beslist zelf wat "toepassen" concreet betekent."""
from __future__ import annotations

from dataclasses import dataclass

from nicegui import ui


@dataclass
class DiffRegel:
    id: str  # unieke sleutel binnen deze diff -- wordt teruggegeven in de aangevinkte set
    omschrijving: str  # bv. "Wo 22 apr: Anne, Bob → Anne, Charlie"
    aangevinkt: bool = True
    groep: str = ""  # optionele kopregel om regels onder te groeperen


async def toon_diff_dialoog(
    titel: str, regels: list[DiffRegel], toepassen_label: str = "Toepassen"
) -> set[str] | None:
    """Toont de regels met een vinkje per stuk. Geeft de set aangevinkte regel-ids terug,
    of None als de gebruiker annuleert of als er niets te tonen was."""
    if not regels:
        ui.notify("Niets om te tonen -- alles is al up-to-date.", type="info")
        return None

    checkboxen: dict[str, ui.checkbox] = {}

    with ui.dialog() as dialoog, ui.card().style("min-width: 480px; max-width: 700px;"):
        ui.label(titel).classes("text-subtitle1")
        with ui.row().classes("q-mb-xs q-gutter-sm"):
            ui.button(
                "Alles aan", on_click=lambda: _zet_alles(checkboxen, True)
            ).props("flat dense")
            ui.button(
                "Alles uit", on_click=lambda: _zet_alles(checkboxen, False)
            ).props("flat dense")

        with ui.scroll_area().style("max-height: 400px; width: 100%;"):
            vorige_groep: object = object()
            for regel in regels:
                if regel.groep and regel.groep != vorige_groep:
                    ui.label(regel.groep).classes("text-caption text-weight-bold q-mt-sm")
                    vorige_groep = regel.groep
                checkboxen[regel.id] = ui.checkbox(regel.omschrijving, value=regel.aangevinkt)

        with ui.row().classes("q-mt-sm justify-end full-width"):
            ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
            ui.button(
                toepassen_label,
                on_click=lambda: dialoog.submit(
                    {rid for rid, cb in checkboxen.items() if cb.value}
                ),
            ).props("color=primary")

    return await dialoog


def _zet_alles(checkboxen: dict[str, ui.checkbox], waarde: bool) -> None:
    for cb in checkboxen.values():
        cb.value = waarde
