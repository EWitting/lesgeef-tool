"""NiceGUI-app: startscherm of de drie-zone-lay-out (docs/DESIGN.md §2.6).

header: projectnaam + opgeslagen-indicator, undo/redo, sluiten.
links:  inklapbare rail -- krijgt in latere fases Jaarplanning/Lesgevers/Beschikbaarheid/
        Config (fase 3, 6, 8). Nu een plek-houder zodat de lay-out al klopt.
midden: de planning, ALTIJD zichtbaar (dit is het hart van de app).
rechts: inspector -- gezondheid/les/persoon (fase 5). Nu leeg."""
from __future__ import annotations

from pathlib import Path

from nicegui import ui
from platformdirs import user_documents_dir

from ..domain.formatting import format_datum_lang
from .bestandsdialoog import kies_bestand_opslaan, native_beschikbaar
from .inspector import Inspector
from .planning_view import PlanningView
from .startscherm import create_startscherm
from .state import state

_LINKS_PANEEL_BREEDTE = "260px"
_RECHTS_PANEEL_BREEDTE = "340px"


@ui.page("/")
def index() -> None:
    ui.add_head_html(
        "<style>.rij-opgelicht { outline: 2px solid #f6ad55; outline-offset: -2px; }</style>"
    )
    root = ui.column().classes("w-full no-wrap").style(
        "height: 100vh; margin: 0; padding: 0; gap: 0;"
    )

    def toon_startscherm() -> None:
        root.clear()
        with root:
            create_startscherm(on_klaar=toon_hoofdscherm)

    def toon_hoofdscherm() -> None:
        root.clear()
        with root:
            _bouw_hoofdlayout(on_sluiten=toon_startscherm)

    if state.doc is not None:
        toon_hoofdscherm()
    else:
        toon_startscherm()


def _bouw_hoofdlayout(on_sluiten) -> None:
    links_zichtbaar = {"waarde": True}

    # Bewust een gewone ui.row() in plaats van ui.header(): ui.header() is een top-level
    # layout-element dat NIET genest mag worden in root (een ui.column()), en we willen de
    # volledige lay-out zelf onder controle houden binnen root.
    with ui.row().classes("items-center justify-between bg-primary full-width").style(
        "padding: 4px 12px; margin: 0; flex-shrink: 0;"
    ):
        with ui.row().classes("items-center q-gutter-sm"):
            ui.button(icon="menu", on_click=lambda: _toggle(links_paneel, links_zichtbaar)).props(
                "flat color=white dense"
            ).tooltip("Linkerpaneel in-/uitklappen")
            projectnaam_label = ui.label(state.doc.project.naam).classes(
                "text-h6 text-white"
            )
            opgeslagen_label = ui.label().classes("text-caption text-white").style(
                "opacity: 0.85;"
            )

        with ui.row().classes("items-center q-gutter-sm"):
            peildatum_label = ui.label().classes("text-caption text-white")
            undo_btn = ui.button(icon="undo", on_click=lambda: _ongedaan_maken()).props(
                "flat color=white dense"
            )
            with undo_btn:
                undo_tooltip = ui.tooltip("Ongedaan maken (Ctrl+Z)")
            redo_btn = ui.button(icon="redo", on_click=lambda: _opnieuw()).props(
                "flat color=white dense"
            )
            with redo_btn:
                redo_tooltip = ui.tooltip("Opnieuw uitvoeren (Ctrl+Y)")
            ui.button(
                "Opslaan", icon="save", on_click=lambda: _opslaan()
            ).props("flat color=white dense")
            ui.button(
                "Sluiten", icon="close", on_click=on_sluiten
            ).props("flat color=white dense")

    with ui.row().classes("w-full no-wrap").style(
        "flex: 1; margin: 0; padding: 0; overflow: hidden; gap: 0;"
    ):
        with ui.column().style(
            f"width: {_LINKS_PANEEL_BREEDTE}; min-width: 220px; height: calc(100vh - 56px); "
            "overflow-y: auto; border-right: 1px solid #e0e0e0; padding: 8px; margin: 0;"
        ) as links_paneel:
            ui.label("Binnenkort hier: Jaarplanning, Lesgevers, Beschikbaarheid, Config.").classes(
                "text-caption text-grey-6"
            )

        with ui.column().style(
            "flex: 1; height: calc(100vh - 56px); overflow-y: auto; padding: 0; margin: 0; "
            "min-width: 0;"
        ) as midden_paneel:
            planning_view = PlanningView(
                midden_paneel,
                on_wijziging_header=lambda: _ververs_na_wijziging(),
                on_selecteer_les=lambda les_id: inspector.toon_les(les_id),
            )
            planning_view.rebuild()

        with ui.column().style(
            f"width: {_RECHTS_PANEEL_BREEDTE}; min-width: 260px; height: calc(100vh - 56px); "
            "overflow-y: auto; border-left: 1px solid #e0e0e0; padding: 8px; margin: 0;"
        ) as rechts_paneel:
            inspector = Inspector(rechts_paneel, planning_view)

    def ververs_header() -> None:
        assert state.doc is not None
        projectnaam_label.set_text(state.doc.project.naam)
        opgeslagen_label.set_text("Niet opgeslagen" if state.doc.gewijzigd else "Opgeslagen")
        peildatum_label.set_text(f"Peildatum: {format_datum_lang(state.peildatum())}")

        volgende_undo = state.doc.volgende_undo_beschrijving()
        undo_btn.props(remove="disable", add="disable" if volgende_undo is None else "")
        undo_tooltip.set_text(
            f"Ongedaan maken: {volgende_undo} (Ctrl+Z)" if volgende_undo else "Niets om ongedaan te maken"
        )

        volgende_redo = state.doc.volgende_redo_beschrijving()
        redo_btn.props(remove="disable", add="disable" if volgende_redo is None else "")
        redo_tooltip.set_text(
            f"Opnieuw uitvoeren: {volgende_redo} (Ctrl+Y)" if volgende_redo else "Niets om opnieuw te doen"
        )

    def _ververs_na_wijziging() -> None:
        """Ververst zowel de header (opgeslagen-indicator, undo/redo) als het
        inspectiepaneel (bevindingen, issue-stippen) -- na ELKE wijziging aan het project,
        ongeacht of die via het middenpaneel, undo/redo, of de solver kwam."""
        ververs_header()
        inspector.render()

    def _ongedaan_maken() -> None:
        assert state.doc is not None
        beschrijving = state.doc.ongedaan_maken()
        if beschrijving is not None:
            ui.notify(f"Ongedaan gemaakt: {beschrijving}", type="info")
            planning_view.rebuild()
            _ververs_na_wijziging()

    def _opnieuw() -> None:
        assert state.doc is not None
        beschrijving = state.doc.opnieuw()
        if beschrijving is not None:
            ui.notify(f"Opnieuw uitgevoerd: {beschrijving}", type="info")
            planning_view.rebuild()
            _ververs_na_wijziging()

    async def _opslaan() -> None:
        assert state.doc is not None
        if state.doc.pad is None:
            await _opslaan_als()
            return
        state.opslaan()
        ui.notify("Opgeslagen.", type="positive")
        ververs_header()

    async def _opslaan_als() -> None:
        assert state.doc is not None
        standaardnaam = f"{state.doc.project.naam}.lesplan"
        if native_beschikbaar():
            pad = await kies_bestand_opslaan(standaardnaam)
            if pad is None:
                return
        else:
            pad = await _vraag_pad_via_dialoog(standaardnaam)
            if pad is None:
                return
        state.opslaan(pad)
        ui.notify(f"Opgeslagen als {pad}", type="positive")
        ververs_header()

    async def _vraag_pad_via_dialoog(standaardnaam: str) -> Path | None:
        """Tekstveld-fallback voor als er geen native venster is (bv. tijdens ontwikkelen)."""
        standaardpad = str(Path(user_documents_dir()) / standaardnaam)
        with ui.dialog() as dialoog, ui.card():
            ui.label("Opslaan als").classes("text-subtitle1")
            veld = ui.input("Bestandspad", value=standaardpad).classes("full-width").style(
                "width: 420px;"
            )
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
                ui.button(
                    "Opslaan", on_click=lambda: dialoog.submit(veld.value)
                ).props("color=primary")
        resultaat = await dialoog
        return Path(resultaat) if resultaat else None

    def _op_toets(e) -> None:
        if not e.action.keydown or not e.modifiers.ctrl or e.modifiers.shift:
            return
        if e.key == "z":
            _ongedaan_maken()
        elif e.key == "y":
            _opnieuw()

    ui.keyboard(on_key=_op_toets)

    state.on_change(lambda: (planning_view.rebuild(), _ververs_na_wijziging()))
    ververs_header()
    ui.timer(5.0, lambda: _autosave_tick(ververs_header))


def _autosave_tick(ververs_header) -> None:
    if state.doc is None:
        return
    if state.doc.autosave_indien_nodig():
        ververs_header()


def _toggle(element: ui.column, zichtbaar_toestand: dict) -> None:
    zichtbaar_toestand["waarde"] = not zichtbaar_toestand["waarde"]
    element.set_visibility(zichtbaar_toestand["waarde"])
