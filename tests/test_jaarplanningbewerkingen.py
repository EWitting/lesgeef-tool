from datetime import date, time

import pytest

from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import jaarplanningbewerkingen as jb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    st = AppState()
    monkeypatch.setattr(jb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def test_voeg_seizoen_toe(state):
    seizoen_id = jb.voeg_seizoen_toe("Voorseizoen 1", date(2026, 4, 19), date(2026, 5, 10))
    assert len(state.doc.project.seizoenen) == 1
    seizoen = state.doc.project.seizoenen[0]
    assert seizoen.id == seizoen_id
    assert seizoen.naam == "Voorseizoen 1"
    assert seizoen.weekrooster is None


def test_wijzig_seizoen(state):
    seizoen_id = jb.voeg_seizoen_toe("S", date(2026, 4, 1), date(2026, 5, 1))
    jb.wijzig_seizoen(seizoen_id, naam="Nieuw", begin=date(2026, 4, 5))
    seizoen = state.doc.project.seizoenen[0]
    assert seizoen.naam == "Nieuw"
    assert seizoen.begin == date(2026, 4, 5)
    assert seizoen.eind == date(2026, 5, 1)


def test_verwijder_seizoen(state):
    seizoen_id = jb.voeg_seizoen_toe("S", date(2026, 4, 1), date(2026, 5, 1))
    jb.verwijder_seizoen(seizoen_id)
    assert state.doc.project.seizoenen == []


def test_zet_eigen_weekrooster_kopieert_jaarrooster(state):
    with state.doc.muteer("setup"):
        from lesgeefplanner.model import WeekSlot

        state.doc.project.weekrooster = [
            WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0))
        ]
    seizoen_id = jb.voeg_seizoen_toe("S", date(2026, 4, 1), date(2026, 5, 1))

    jb.zet_eigen_weekrooster(seizoen_id, True)
    seizoen = state.doc.project.seizoenen[0]
    assert seizoen.weekrooster == state.doc.project.weekrooster
    assert seizoen.weekrooster is not state.doc.project.weekrooster  # kopie, geen alias

    jb.zet_eigen_weekrooster(seizoen_id, False)
    assert state.doc.project.seizoenen[0].weekrooster is None


def test_weekslot_toevoegen_en_verwijderen_jaarrooster(state):
    jb.voeg_weekslot_toe(None, dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    assert len(state.doc.project.weekrooster) == 1
    jb.verwijder_weekslot(None, 0)
    assert state.doc.project.weekrooster == []


def test_weekslot_toevoegen_seizoen_zonder_eigen_weekrooster_doet_niets(state):
    seizoen_id = jb.voeg_seizoen_toe("S", date(2026, 4, 1), date(2026, 5, 1))
    jb.voeg_weekslot_toe(seizoen_id, dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    assert state.doc.project.seizoenen[0].weekrooster is None


def test_weekslot_toevoegen_aan_eigen_weekrooster(state):
    seizoen_id = jb.voeg_seizoen_toe("PKursus", date(2026, 3, 16), date(2026, 4, 19))
    jb.zet_eigen_weekrooster(seizoen_id, True)
    jb.voeg_weekslot_toe(seizoen_id, dag=0, begin_tijd=time(19, 0), eind_tijd=time(21, 0))
    seizoen = state.doc.project.seizoenen[0]
    assert len(seizoen.weekrooster) == 1
    assert seizoen.weekrooster[0].dag == 0
