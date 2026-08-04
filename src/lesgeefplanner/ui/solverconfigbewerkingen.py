"""Bewerkingen op SolverConfig. Eén object in plaats van een lijst, dus simpeler dan de
andere *bewerkingen.py-modules: de UI bouwt een nieuwe SolverConfig en dit vervangt hem in
zijn geheel via doc.muteer(), net zo testbaar en UI-onafhankelijk als de rest."""
from __future__ import annotations

from ..model.config import SolverConfig
from .state import state


def wijzig_solver_config(nieuwe_config: SolverConfig) -> None:
    assert state.doc is not None
    with state.doc.muteer("Solver-instellingen aangepast"):
        state.doc.project.solver_config = nieuwe_config


def reset_solver_config() -> None:
    assert state.doc is not None
    with state.doc.muteer("Solver-instellingen teruggezet naar standaard"):
        state.doc.project.solver_config = SolverConfig()
