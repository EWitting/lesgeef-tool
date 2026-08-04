"""Gedeelde werkverdeling-berekening. Gebruikt door de solver (planner/solve.py, als
CP-SAT-constraint), de analyse (domain/analysis.py, als bevinding) en het inspectiepaneel
(ui/inspector.py, als balkdiagram) -- allemaal dezelfde definitie van "doel", anders lijkt
de app zichzelf tegen te spreken (de solver optimaliseert tegen een ander getal dan wat de
gebruiker op het scherm ziet)."""
from __future__ import annotations

from ..model.entities import Les, les_seizoen_id
from ..model.project import Project


def bereken_doel(richtlijn_lessen_per_week: float, aantal_weken: int) -> int:
    """Hoeveel lessen een lesgever 'hoort' te geven, gegeven de richtlijn en de lengte van
    het seizoen in weken. Minimaal 1, ook bij een erg korte richtlijn/seizoen."""
    return max(1, round(richtlijn_lessen_per_week * aantal_weken))


def lessen_per_seizoen(project: Project) -> dict[str | None, list[Les]]:
    """Alle lessen die doorgaan, gegroepeerd op seizoen (None = geen seizoen)."""
    resultaat: dict[str | None, list[Les]] = {}
    for les in project.lessen:
        if les.status != "gaat_door":
            continue
        resultaat.setdefault(les_seizoen_id(les), []).append(les)
    return resultaat


def doel_voor_seizoen(project: Project, lessen_dit_seizoen: list[Les]) -> int:
    weken = {les.datum.isocalendar()[:2] for les in lessen_dit_seizoen}
    return bereken_doel(project.solver_config.richtlijn_lessen_per_week, len(weken) if weken else 1)


def totaal_voor_lesgever(lesgever_id: str, lessen: list[Les]) -> int:
    return sum(1 for les in lessen for tw in les.toewijzingen if tw.lesgever_id == lesgever_id)
