"""Datamodel voor Lesgeefplanner. Zie docs/DESIGN.md §3 voor de achtergrond."""
from __future__ import annotations

from .ids import nieuw_id
from .config import SolverConfig
from .entities import Herkomst, Les, Lesgever, Seizoen, Toewijzing, WeekSlot
from .availability import Antwoord, Antwoordwaarde, Ronde, RondeVraag
from .scope import Scope
from .project import Project, Werkblad

__all__ = [
    "nieuw_id",
    "SolverConfig",
    "Herkomst",
    "Les",
    "Lesgever",
    "Seizoen",
    "Toewijzing",
    "WeekSlot",
    "Antwoord",
    "Antwoordwaarde",
    "Ronde",
    "RondeVraag",
    "Scope",
    "Project",
    "Werkblad",
]
