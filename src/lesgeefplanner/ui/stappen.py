"""Stappenstatus voor de linkerrail: klaar / aandacht / leeg per onderdeel, op basis van de
huidige projecttoestand. Zie docs/DESIGN.md §7 en docs/PLAN.md fase 9 ("iemand die de app
nooit zag, komt er zelf uit" -- de status laat in één oogopslag zien wat de volgende
zinvolle stap is)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from ..domain.analysis import analyseer
from ..domain.calendar import bereken_kalender_diff, gewenste_lessen
from ..model.project import Project
from ..model.scope import Scope

StapStatus = Literal["klaar", "aandacht", "leeg"]

_ICOON = {"klaar": "✓", "aandacht": "!", "leeg": "—"}


def icoon(status: StapStatus) -> str:
    return _ICOON[status]


def stap_jaarplanning(project: Project) -> StapStatus:
    if not project.seizoenen:
        return "leeg"
    if not gewenste_lessen(project):
        return "aandacht"
    if not bereken_kalender_diff(project).is_leeg():
        return "aandacht"
    return "klaar"


def stap_lesgevers(project: Project) -> StapStatus:
    if not project.lesgevers:
        return "leeg"
    if not any(lg.actief for lg in project.lesgevers):
        return "aandacht"
    return "klaar"


def stap_beschikbaarheid(project: Project) -> StapStatus:
    if not project.rondes:
        return "leeg"
    if not any(ronde.antwoorden for ronde in project.rondes):
        return "aandacht"
    return "klaar"


def stap_inroosteren(project: Project, peildatum: date) -> StapStatus:
    bevindingen = analyseer(project, Scope(), peildatum)
    if any(b.ernst == "fout" for b in bevindingen):
        return "aandacht"
    heeft_toewijzingen = any(
        les.toewijzingen for les in project.lessen if les.status == "gaat_door"
    )
    return "klaar" if heeft_toewijzingen else "leeg"


def stap_delen(project: Project) -> StapStatus:
    return "klaar" if project.werkblad.laatste_export_pad else "leeg"


def alle_stappen(project: Project, peildatum: date) -> dict[str, StapStatus]:
    return {
        "Jaarplanning": stap_jaarplanning(project),
        "Lesgevers": stap_lesgevers(project),
        "Beschikbaarheid": stap_beschikbaarheid(project),
        "Inroosteren": stap_inroosteren(project, peildatum),
        "Delen": stap_delen(project),
    }
