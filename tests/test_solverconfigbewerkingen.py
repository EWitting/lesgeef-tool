import pytest

from lesgeefplanner.model.config import SolverConfig
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import solverconfigbewerkingen as scb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    st = AppState()
    monkeypatch.setattr(scb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def test_wijzig_solver_config(state):
    nieuw = SolverConfig(lesgever_minimum=3, lesgever_maximum=4)
    scb.wijzig_solver_config(nieuw)
    assert state.doc.project.solver_config.lesgever_minimum == 3
    assert state.doc.project.solver_config.lesgever_maximum == 4


def test_reset_solver_config(state):
    scb.wijzig_solver_config(SolverConfig(lesgever_minimum=9))
    assert state.doc.project.solver_config.lesgever_minimum == 9

    scb.reset_solver_config()
    assert state.doc.project.solver_config == SolverConfig()


def test_wijzig_solver_config_is_undoable(state):
    origineel = state.doc.project.solver_config.model_copy()
    scb.wijzig_solver_config(SolverConfig(lesgever_minimum=9))
    beschrijving = state.doc.ongedaan_maken()
    assert beschrijving == "Solver-instellingen aangepast"
    assert state.doc.project.solver_config == origineel
