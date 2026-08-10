"""De scope-balk: welke lessenreeksen en welk tijdvenster "Automatisch invullen" (fase 4),
het aanmaken van een beschikbaarheidsronde (fase 6) en het statuspaneel (fase 5) raken.
Zie docs/DESIGN.md §2.4 -- één gedeeld begrip in plaats van drie losse instellingen, zodat
een knop nooit een ander deel van de planning raakt dan wat er op het scherm getoond wordt.

Dit is de widget zelf (herbruikbaar); zowel het middenpaneel als de "Nieuwe ronde"-kaart in
rondes.py roepen 'm apart aan, dus wijzigen op de ene plek werkt meteen door naar de andere
(dezelfde onderliggende Scope via state.scope/state.stel_scope_in)."""
from __future__ import annotations

from nicegui import ui

from ...model.scope import Scope
from ..state import state


def create_scope_balk(container: ui.row) -> None:
    """Wijzigen roept `state.stel_scope_in()` aan, die zelf `state.meld_wijziging()`
    aanroept -- dat rebuildt via de bestaande state.on_change-keten o.a. het middenpaneel
    (dus ook deze balk zelf, met de nieuwe waarde) en het gezondheidspaneel. Geen aparte
    callback nodig."""
    container.clear()
    if state.doc is None:
        return
    project = state.doc.project
    scope = state.scope

    with container:
        ui.icon("filter_alt").classes("text-grey-7").tooltip(
            "Selectie: bepaalt wat 'Automatisch invullen', een nieuwe datumprikker, "
            "en het statuspaneel raken. Lessen buiten de selectie krijgen geen gekleurde "
            "rand in de kalender."
        )
        seizoen_opties = {s.id: s.naam for s in project.seizoenen}
        seizoen_select = ui.select(
            seizoen_opties, value=scope.seizoen_ids, multiple=True,
            label="Lessenreeksen (leeg = alle)",
        ).props("dense outlined use-chips").style("min-width: 240px;")
        toekomst_toggle = ui.checkbox(
            "Alleen toekomstige lessen", value=scope.alleen_toekomst
        )

        def _wijzig(_e=None) -> None:
            nieuwe_scope = Scope(
                seizoen_ids=seizoen_select.value or None,
                alleen_toekomst=toekomst_toggle.value,
            )
            state.stel_scope_in(nieuwe_scope)

        seizoen_select.on_value_change(_wijzig)
        toekomst_toggle.on_value_change(_wijzig)
