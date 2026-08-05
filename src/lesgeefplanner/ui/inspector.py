"""Rechterpaneel: gezondheid van de scope, of details van een geselecteerde les/persoon.
Zie docs/DESIGN.md §5 en docs/PLAN.md fase 5.

Drie standen (nooit tegelijk):
- niets geselecteerd -> gezondheid: bevindingen per ernst, belasting-per-persoon-balken,
  "waarom deze score?".
- een les geselecteerd -> wie beschikbaar is, de bevindingen van die les, de solver-uitleg.
- een lesgever geselecteerd -> hun belasting per seizoen, hun lessen dit jaar."""
from __future__ import annotations

import json

from nicegui import ui

from ..domain.analysis import Bevinding, analyseer
from ..domain.beschikbaarheid import verzamel_beschikbaarheid
from ..domain.formatting import format_datum_lang, format_tijdvak
from ..domain.report import genereer_tekstrapport
from ..domain.werkverdeling import doel_voor_seizoen, lessen_per_seizoen, totaal_voor_lesgever
from ..model.entities import les_seizoen_id
from ..planner.terms import CATEGORIE_LABELS
from .planning_view import PlanningView
from .state import state

_ERNST_LABEL = {"fout": "Fouten", "waarschuwing": "Waarschuwingen", "info": "Info"}
_ERNST_ICOON = {"fout": "error", "waarschuwing": "warning", "info": "info"}
_ERNST_KLEUR = {"fout": "text-red-8", "waarschuwing": "text-orange-8", "info": "text-blue-8"}
_BESCHIKBAARHEID_LABEL = {"ja": "Ja", "misschien": "Misschien", "nee": "Nee"}


def _per_les(bevindingen: list[Bevinding]) -> dict[str, list[Bevinding]]:
    resultaat: dict[str, list[Bevinding]] = {}
    for b in bevindingen:
        if b.les_id is not None:
            resultaat.setdefault(b.les_id, []).append(b)
    return resultaat


class Inspector:
    def __init__(self, container: ui.column, planning_view: PlanningView) -> None:
        self._container = container
        self._planning_view = planning_view
        self._modus: str = "gezondheid"  # "gezondheid" | "les" | "lesgever"
        self._geselecteerd_id: str | None = None
        self.render()

    # ------------------------------------------------------------------
    # Navigatie -- aangeroepen vanuit planning_view (klik op een rij) en vanuit zichzelf
    # (klik op een bevinding of een persoon)
    # ------------------------------------------------------------------

    def toon_gezondheid(self) -> None:
        self._modus = "gezondheid"
        self._geselecteerd_id = None
        self.render()

    def toon_les(self, les_id: str) -> None:
        self._modus = "les"
        self._geselecteerd_id = les_id
        self.render()

    def toon_lesgever(self, lesgever_id: str) -> None:
        self._modus = "lesgever"
        self._geselecteerd_id = lesgever_id
        self.render()

    # ------------------------------------------------------------------

    def render(self) -> None:
        self._container.clear()
        if state.doc is None:
            with self._container:
                ui.label("Geen project geopend.").classes("text-grey-6")
            return

        project = state.doc.project
        scope = state.scope
        peildatum = state.peildatum()
        bevindingen = analyseer(project, scope, peildatum)
        self._planning_view.stel_bevindingen_in(_per_les(bevindingen))

        with self._container:
            les = None
            lesgever = None
            if self._modus == "les" and self._geselecteerd_id:
                les = next((l for l in project.lessen if l.id == self._geselecteerd_id), None)
            elif self._modus == "lesgever" and self._geselecteerd_id:
                lesgever = next(
                    (l for l in project.lesgevers if l.id == self._geselecteerd_id), None
                )

            if les is not None:
                self._render_les(project, les, bevindingen)
            elif lesgever is not None:
                self._render_lesgever(project, lesgever)
            else:
                self._render_gezondheid(project, bevindingen)

    # ------------------------------------------------------------------
    # Stand 1: gezondheid
    # ------------------------------------------------------------------

    def _render_gezondheid(self, project, bevindingen: list[Bevinding]) -> None:
        with ui.row().classes("items-center justify-between full-width"):
            ui.label("Status").classes("text-h6")
            ui.button(
                icon="content_copy", on_click=lambda: self._kopieer_rapport(bevindingen)
            ).props("flat dense").tooltip("Kopieer rapport")

        if not bevindingen:
            ui.label("Geen bijzonderheden gevonden.").classes("text-positive q-mt-sm")
        else:
            for ernst in ("fout", "waarschuwing", "info"):
                groep = [b for b in bevindingen if b.ernst == ernst]
                if not groep:
                    continue
                with ui.row().classes("items-center q-gutter-xs q-mt-sm"):
                    ui.icon(_ERNST_ICOON[ernst]).classes(_ERNST_KLEUR[ernst])
                    ui.label(f"{_ERNST_LABEL[ernst]} ({len(groep)})").classes("text-weight-bold")
                for b in groep:
                    self._bevinding_regel(b)

        ui.separator().classes("q-my-md")
        ui.label("Belasting per persoon").classes("text-subtitle2")
        self._render_belasting(project)

        ui.separator().classes("q-my-md")
        ui.label("Waarom deze score?").classes("text-subtitle2")
        self._render_score_verdeling()

    def _bevinding_regel(self, b: Bevinding) -> None:
        with ui.row().classes("items-center cursor-pointer q-py-1 full-width").on(
            "click", lambda: self._klik_bevinding(b)
        ) as rij:
            ui.label(b.titel).classes("text-caption")
        rij.tooltip(b.uitleg)

    def _klik_bevinding(self, b: Bevinding) -> None:
        if b.les_id:
            self._planning_view.scroll_en_licht_op(b.les_id)
            self.toon_les(b.les_id)
        elif b.lesgever_id:
            self.toon_lesgever(b.lesgever_id)

    def _kopieer_rapport(self, bevindingen: list[Bevinding]) -> None:
        tekst = genereer_tekstrapport(bevindingen)
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(tekst)})")
        ui.notify("Rapport gekopieerd naar klembord.", type="positive")

    def _render_belasting(self, project) -> None:
        scope = state.scope
        peildatum = state.peildatum()
        lessen_in_scope = [
            l for l in project.lessen if l.status == "gaat_door" and scope.bevat(l, peildatum)
        ]
        seizoenen_in_scope = {les_seizoen_id(l) for l in lessen_in_scope}
        per_seizoen = lessen_per_seizoen(project)

        gegevens: list[tuple[str, str, int, int]] = []
        for lg in sorted((l for l in project.lesgevers if l.actief), key=lambda l: l.naam.lower()):
            totaal = 0
            doel = 0
            for sleutel in seizoenen_in_scope:
                lessen = per_seizoen.get(sleutel, [])
                doel += doel_voor_seizoen(project, lessen)
                totaal += totaal_voor_lesgever(lg.id, lessen)
            gegevens.append((lg.naam, lg.id, totaal, doel))

        if not gegevens:
            ui.label("Geen actieve lesgevers.").classes("text-caption text-grey-6")
            return

        max_waarde = max((max(t, d) for _, _, t, d in gegevens), default=1) or 1
        for naam, lg_id, totaal, doel in gegevens:
            with ui.row().classes("items-center cursor-pointer").style("gap: 6px;").on(
                "click", lambda lg_id=lg_id: self.toon_lesgever(lg_id)
            ):
                ui.label(naam).classes("text-caption").style(
                    "width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                )
                with ui.element("div").style(
                    "position: relative; flex: 1; height: 14px; background: #e5e5e5; "
                    "border-radius: 3px;"
                ):
                    breedte_pct = min(100, round(totaal / max_waarde * 100))
                    if totaal > doel:
                        kleur = "#e53e3e"
                    elif totaal < doel:
                        kleur = "#3182ce"
                    else:
                        kleur = "#38a169"
                    ui.element("div").style(
                        f"position: absolute; left: 0; top: 0; height: 100%; "
                        f"width: {breedte_pct}%; background: {kleur}; border-radius: 3px;"
                    )
                    doel_pct = min(100, round(doel / max_waarde * 100))
                    ui.element("div").style(
                        f"position: absolute; left: {doel_pct}%; top: -2px; height: 18px; "
                        f"width: 2px; background: #333;"
                    )
                ui.label(f"{totaal}/{doel}").classes("text-caption").style("width: 40px;")

    def _render_score_verdeling(self) -> None:
        result = state.laatste_plan_result
        if result is None:
            ui.label(
                "Nog niet automatisch ingevuld -- draai de solver om de score-opbouw te zien."
            ).classes("text-caption text-grey-6")
            return
        ui.label(f"Totale score: {result.score:.1f} ({result.status})").classes(
            "text-caption q-mb-xs"
        )
        for categorie, bijdrage in sorted(result.verdeling.items(), key=lambda kv: -abs(kv[1])):
            if bijdrage == 0:
                continue
            with ui.row().classes("items-center justify-between full-width"):
                ui.label(CATEGORIE_LABELS.get(categorie, categorie)).classes("text-caption")
                ui.label(f"{bijdrage:+.1f}").classes("text-caption")

    # ------------------------------------------------------------------
    # Stand 2: een les
    # ------------------------------------------------------------------

    def _render_les(self, project, les, bevindingen: list[Bevinding]) -> None:
        ui.button("← Status", on_click=self.toon_gezondheid).props("flat dense no-caps")

        ui.label(format_datum_lang(les.datum)).classes("text-h6")
        ui.label(format_tijdvak(les.begin_tijd, les.eind_tijd)).classes(
            "text-caption text-grey-7"
        )
        if les.titel:
            ui.label(les.titel).classes("text-caption")
        if les.status == "vervallen":
            reden = f" — {les.vervallen_reden}" if les.vervallen_reden else ""
            ui.label(f"Vervalt{reden}").classes("text-caption text-negative")

        ui.separator().classes("q-my-sm")
        ui.label("Beschikbaarheid").classes("text-subtitle2")
        beschikbaarheid = verzamel_beschikbaarheid(project)
        toegewezen_ids = {tw.lesgever_id for tw in les.toewijzingen}
        for lg in sorted((l for l in project.lesgevers if l.actief), key=lambda l: l.naam.lower()):
            waarde = beschikbaarheid.get((lg.id, les.id))
            label = _BESCHIKBAARHEID_LABEL.get(waarde, "Onbekend")
            ingedeeld = " (ingedeeld)" if lg.id in toegewezen_ids else ""
            with ui.row().classes("items-center justify-between full-width cursor-pointer").on(
                "click", lambda lg_id=lg.id: self.toon_lesgever(lg_id)
            ):
                ui.label(f"{lg.naam}{ingedeeld}").classes("text-caption")
                ui.label(label).classes("text-caption")

        les_bevindingen = [b for b in bevindingen if b.les_id == les.id]
        if les_bevindingen:
            ui.separator().classes("q-my-sm")
            ui.label("Bevindingen").classes("text-subtitle2")
            for b in les_bevindingen:
                ui.label(f"• {b.titel}").classes("text-caption")

        result = state.laatste_plan_result
        if result is not None:
            uitleg = result.per_les.get(les.id, [])
            if uitleg:
                lesgever_by_id = {lg.id: lg for lg in project.lesgevers}
                ui.separator().classes("q-my-sm")
                ui.label("Solver-uitleg (laatste run)").classes("text-subtitle2")
                for u in uitleg:
                    naam_toevoeging = ""
                    if u.lesgever_id and u.lesgever_id in lesgever_by_id:
                        naam_toevoeging = f" ({lesgever_by_id[u.lesgever_id].naam})"
                    ui.label(f"• {u.tekst}{naam_toevoeging}: {u.bijdrage:+.1f}").classes(
                        "text-caption"
                    )

    # ------------------------------------------------------------------
    # Stand 3: een lesgever
    # ------------------------------------------------------------------

    def _render_lesgever(self, project, lesgever) -> None:
        ui.button("← Status", on_click=self.toon_gezondheid).props("flat dense no-caps")

        ui.label(lesgever.naam).classes("text-h6")
        ui.label(f"Ervaring: {lesgever.ervaring_jaren} jaar").classes("text-caption text-grey-7")

        beschikbaarheid = verzamel_beschikbaarheid(project)
        tellingen = {"ja": 0, "misschien": 0, "nee": 0}
        for les in project.lessen:
            if les.status != "gaat_door":
                continue
            waarde = beschikbaarheid.get((lesgever.id, les.id))
            if waarde in tellingen:
                tellingen[waarde] += 1
        ui.label(
            f"Beschikbaarheid: {tellingen['ja']}x ja, {tellingen['misschien']}x misschien, "
            f"{tellingen['nee']}x nee"
        ).classes("text-caption text-grey-7")

        ui.separator().classes("q-my-sm")
        ui.label("Belasting per seizoen").classes("text-subtitle2")
        per_seizoen = lessen_per_seizoen(project)
        seizoen_naam = {s.id: s.naam for s in project.seizoenen}
        for sleutel, lessen in per_seizoen.items():
            totaal = totaal_voor_lesgever(lesgever.id, lessen)
            doel = doel_voor_seizoen(project, lessen)
            naam = seizoen_naam.get(sleutel, "Geen seizoen")
            ui.label(f"{naam}: {totaal}/{doel}").classes("text-caption")

        ui.separator().classes("q-my-sm")
        ui.label("Lessen dit jaar").classes("text-subtitle2")
        eigen_lessen = sorted(
            (
                les
                for les in project.lessen
                if les.status == "gaat_door"
                and any(tw.lesgever_id == lesgever.id for tw in les.toewijzingen)
            ),
            key=lambda l: l.datum,
        )
        if not eigen_lessen:
            ui.label("Nog geen lessen.").classes("text-caption text-grey-6")
        for les in eigen_lessen:
            with ui.row().classes("items-center justify-between full-width cursor-pointer").on(
                "click", lambda les_id=les.id: self._klik_les(les_id)
            ):
                ui.label(format_datum_lang(les.datum)).classes("text-caption")

    def _klik_les(self, les_id: str) -> None:
        self._planning_view.scroll_en_licht_op(les_id)
        self.toon_les(les_id)
