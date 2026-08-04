"""Resultaat van een solver-run. Zie docs/DESIGN.md §4.2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .terms import Uitleg


@dataclass
class PlanResult:
    status: Literal["optimaal", "haalbaar", "onhaalbaar"]
    minimum_afgedwongen: bool
    toewijzingen: dict[str, list[str]] = field(default_factory=dict)  # les_id -> [lesgever_id]
    score: float = 0.0
    verdeling: dict[str, float] = field(default_factory=dict)  # categorie -> bijdrage
    per_les: dict[str, list[Uitleg]] = field(default_factory=dict)
    rekentijd: float = 0.0
