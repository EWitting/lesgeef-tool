"""Gedeelde UI-status: het huidige Document, de actieve scope en peildatum.

Niet met naam genoemd in docs/DESIGN.md §7 (zie docs/BESLISSINGEN.md); toegevoegd omdat de
losse ui/-modules een gezamenlijke plek nodig hebben. Dit is een lokale, single-user
desktop-app (§2.7), dus één instantie per proces is voldoende -- er is geen sprake van
meerdere gelijktijdige gebruikers die elkaars state niet mogen zien."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from ..model import Project, Scope
from ..planner import PlanResult
from ..store.document import Document
from ..store.instellingen import voeg_recent_bestand_toe


class AppState:
    def __init__(self) -> None:
        self.doc: Document | None = None
        # Resultaat van de laatst gedraaide solver-run, ook als het voorstel niet (volledig)
        # is toegepast -- het inspectiepaneel toont hiermee "waarom deze score?" en de
        # per-les Uitleg (docs/DESIGN.md §5) zonder de solver opnieuw te hoeven draaien.
        self.laatste_plan_result: PlanResult | None = None
        self._on_change: list[Callable[[], None]] = []

    @property
    def scope(self) -> Scope:
        assert self.doc is not None
        return self.doc.project.werkblad.laatste_scope

    def peildatum(self) -> date:
        if self.doc is not None and self.doc.project.werkblad.peildatum_override is not None:
            return self.doc.project.werkblad.peildatum_override
        return date.today()

    def nieuw_project(self, naam: str) -> None:
        self.doc = Document.nieuw(naam)
        self.laatste_plan_result = None
        self._meld_wijziging()

    def open_project(self, pad: Path) -> None:
        self.doc = Document.open(pad)
        self.laatste_plan_result = None
        voeg_recent_bestand_toe(pad)
        self._meld_wijziging()

    def stel_project_in(self, project: Project) -> None:
        """Voor projecten die niet uit een .lesplan-bestand komen, maar zijn opgebouwd
        door code (jaarwissel, legacy-import): geen pad totdat de gebruiker opslaat."""
        self.doc = Document(project)
        self.laatste_plan_result = None
        self._meld_wijziging()

    def opslaan(self, pad: Path | None = None) -> None:
        assert self.doc is not None
        self.doc.opslaan(pad)
        if self.doc.pad is not None:
            voeg_recent_bestand_toe(self.doc.pad)
        self._meld_wijziging()

    def on_change(self, fn: Callable[[], None]) -> None:
        self._on_change.append(fn)

    def meld_wijziging(self) -> None:
        """Door UI-code aan te roepen na een mutatie via doc.muteer(), zodat alle
        geabonneerde views zichzelf verversen."""
        self._meld_wijziging()

    def _meld_wijziging(self) -> None:
        for fn in list(self._on_change):
            fn()


state = AppState()
