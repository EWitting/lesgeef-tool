"""Instellingen voor de solver. Zie docs/DESIGN.md §3.7."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SolverConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesgever_minimum: int = 2
    lesgever_maximum: int = 3
    lesgever_bonus: float = 3
    penalty_lesgever_tekort: float = 10
    penalty_misschien: float = 8
    penalty_geen_ervaren_lesgever: float = 5
    penalty_meerdere_lessen_per_week: float = 8
    richtlijn_lessen_per_week: float = 0.4
    penalty_boven_richtlijn: float = 4
    penalty_onder_richtlijn: float = 2
    penalty_verdeling_stappen: list[float] = [1, 2, 3, 4, 5]
    penalty_wijziging: float = 6
    max_rekentijd_seconden: float = 30
