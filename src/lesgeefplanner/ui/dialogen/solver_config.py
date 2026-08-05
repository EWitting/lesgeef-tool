"""Solver-instellingen: minimum/maximum lesgevers per les en de penalty-gewichten die
"Automatisch invullen" (planner/solve.py) afweegt. Zit achter een klein knopje in plaats
van een vast paneel in de linkerrail, omdat de meeste commissies de getunede
standaardwaarden nooit hoeven aan te passen -- zie docs/BESLISSINGEN.md."""
from __future__ import annotations

from nicegui import ui

from ...model.config import SolverConfig
from .. import solverconfigbewerkingen as scb
from ..state import state

# (veldnaam, label, groep) -- bepaalt zowel volgorde als groepskopjes in de dialoog.
_VELDEN: list[tuple[str, str, str]] = [
    ("lesgever_minimum", "Minimum lesgevers per les", "Bezetting"),
    ("lesgever_maximum", "Maximum lesgevers per les", "Bezetting"),
    ("lesgever_bonus", "Bonus per extra lesgever", "Bezetting"),
    ("penalty_lesgever_tekort", "Penalty: te weinig lesgevers", "Bezetting"),
    ("penalty_misschien", "Penalty: 'misschien' ingedeeld", "Beschikbaarheid"),
    ("penalty_geen_ervaren_lesgever", "Penalty: geen ervaren lesgever", "Ervaring"),
    ("penalty_meerdere_lessen_per_week", "Penalty: meerdere lessen per week", "Werkverdeling"),
    ("richtlijn_lessen_per_week", "Richtlijn lessen per week (per lesgever)", "Werkverdeling"),
    ("penalty_boven_richtlijn", "Penalty: boven de richtlijn (per stap)", "Werkverdeling"),
    ("penalty_onder_richtlijn", "Penalty: onder de richtlijn (per stap)", "Werkverdeling"),
    ("penalty_wijziging", "Penalty: bestaande toewijzing loslaten", "Stabiliteit"),
    ("max_rekentijd_seconden", "Maximale rekentijd (seconden)", "Overig"),
]


def create_solver_config_knop(container: ui.element, kleur: str | None = None) -> None:
    """Klein knopje dat de instellingen-dialoog opent. Geen apart paneel in de rail."""
    with container:
        props = "flat dense round"
        if kleur:
            props += f" color={kleur}"
        ui.button(icon="tune", on_click=_open_dialoog).props(props).tooltip(
            "Solver-instellingen"
        )


def _open_dialoog() -> None:
    assert state.doc is not None
    cfg = state.doc.project.solver_config
    velden: dict[str, ui.number] = {}

    with ui.dialog() as dialoog, ui.card().style("min-width: 420px; max-width: 520px;"):
        ui.label("Solver-instellingen").classes("text-subtitle1")
        ui.label(
            "Bepalen hoe 'Automatisch invullen' afweegt. De standaardwaarden zijn getuned "
            "en werken voor de meeste seizoenen prima -- pas ze alleen aan als je weet wat "
            "je doet."
        ).classes("text-caption text-grey-7 q-mb-sm")

        with ui.scroll_area().style("max-height: 50vh;").classes("full-width"):
            huidige_groep: str | None = None
            for veldnaam, label, groep in _VELDEN:
                if groep != huidige_groep:
                    ui.label(groep).classes("text-caption text-weight-bold q-mt-sm")
                    huidige_groep = groep
                waarde = getattr(cfg, veldnaam)
                stap = 1 if isinstance(waarde, int) else 0.5
                velden[veldnaam] = ui.number(
                    label, value=waarde, step=stap, min=0
                ).props("dense outlined").classes("full-width")

            ui.label("Werkverdeling").classes("text-caption text-weight-bold q-mt-sm")
            stappen_veld = ui.input(
                "Stapgroottes boven/onder richtlijn (komma-gescheiden)",
                value=", ".join(str(s) for s in cfg.penalty_verdeling_stappen),
            ).props("dense outlined").classes("full-width")

        with ui.row().classes("q-mt-md justify-between full-width"):
            ui.button(
                "Terug naar standaard", icon="restore",
                on_click=lambda: _klik_reset(dialoog),
            ).props("flat color=negative no-caps")
            with ui.row().classes("q-gutter-sm"):
                ui.button("Annuleren", on_click=dialoog.close).props("flat no-caps")
                ui.button(
                    "Opslaan",
                    on_click=lambda: _klik_opslaan(dialoog, velden, stappen_veld),
                ).props("color=primary no-caps")

    dialoog.open()


def _klik_reset(dialoog: ui.dialog) -> None:
    scb.reset_solver_config()
    ui.notify("Solver-instellingen teruggezet naar standaard.", type="positive")
    state.meld_wijziging()
    dialoog.close()


def _klik_opslaan(
    dialoog: ui.dialog, velden: dict[str, ui.number], stappen_veld: ui.input
) -> None:
    try:
        stappen = [float(s.strip()) for s in stappen_veld.value.split(",") if s.strip()]
        if not stappen:
            raise ValueError
    except ValueError:
        ui.notify(
            "Ongeldige stapgroottes -- gebruik komma-gescheiden getallen.", type="warning"
        )
        return

    waarden = {naam: veld.value for naam, veld in velden.items()}
    if any(w is None for w in waarden.values()):
        ui.notify("Vul alle velden in.", type="warning")
        return
    if waarden["lesgever_maximum"] < waarden["lesgever_minimum"]:
        ui.notify("Maximum kan niet kleiner zijn dan minimum.", type="warning")
        return

    nieuwe_config = SolverConfig(
        lesgever_minimum=int(waarden["lesgever_minimum"]),
        lesgever_maximum=int(waarden["lesgever_maximum"]),
        lesgever_bonus=waarden["lesgever_bonus"],
        penalty_lesgever_tekort=waarden["penalty_lesgever_tekort"],
        penalty_misschien=waarden["penalty_misschien"],
        penalty_geen_ervaren_lesgever=waarden["penalty_geen_ervaren_lesgever"],
        penalty_meerdere_lessen_per_week=waarden["penalty_meerdere_lessen_per_week"],
        richtlijn_lessen_per_week=waarden["richtlijn_lessen_per_week"],
        penalty_boven_richtlijn=waarden["penalty_boven_richtlijn"],
        penalty_onder_richtlijn=waarden["penalty_onder_richtlijn"],
        penalty_verdeling_stappen=stappen,
        penalty_wijziging=waarden["penalty_wijziging"],
        max_rekentijd_seconden=waarden["max_rekentijd_seconden"],
    )
    scb.wijzig_solver_config(nieuwe_config)
    ui.notify("Solver-instellingen opgeslagen.", type="positive")
    state.meld_wijziging()
    dialoog.close()
