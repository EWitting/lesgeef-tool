from datetime import date, time

import pytest

from lesgeefplanner.model.entities import Les, Toewijzing
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import lesgeverbewerkingen as lgb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    st = AppState()
    monkeypatch.setattr(lgb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def test_voeg_lesgever_toe(state):
    lg_id = lgb.voeg_lesgever_toe("  Anne  ")
    assert len(state.doc.project.lesgevers) == 1
    lg = state.doc.project.lesgevers[0]
    assert lg.id == lg_id
    assert lg.naam == "Anne"
    assert lg.actief is True
    assert lg.ervaring_jaren == 0


def test_wijzig_lesgever(state):
    lg_id = lgb.voeg_lesgever_toe("Anne")
    lgb.wijzig_lesgever(lg_id, naam="Anne de Vries", ervaring_jaren=3, actief=False)
    lg = state.doc.project.lesgevers[0]
    assert lg.naam == "Anne de Vries"
    assert lg.ervaring_jaren == 3
    assert lg.actief is False


def test_wijzig_lesgever_leeg_naam_wordt_genegeerd(state):
    lg_id = lgb.voeg_lesgever_toe("Anne")
    lgb.wijzig_lesgever(lg_id, naam="   ")
    assert state.doc.project.lesgevers[0].naam == "Anne"


def test_verwijder_lesgever_ruimt_toewijzingen_op(state):
    lg_id = lgb.voeg_lesgever_toe("Anne")
    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        toewijzingen=[Toewijzing(lesgever_id=lg_id, vast=True)],
    )
    with state.doc.muteer("setup"):
        state.doc.project.lessen.append(les)

    lgb.verwijder_lesgever(lg_id)

    assert state.doc.project.lesgevers == []
    assert state.doc.project.lessen[0].toewijzingen == []
