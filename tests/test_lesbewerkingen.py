from datetime import date, time

import pytest

from lesgeefplanner.model import Lesgever
from lesgeefplanner.model.entities import Les, Toewijzing
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import lesbewerkingen as lb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    """Een verse AppState per test, zodat tests elkaar niet raken via de module-singleton."""
    st = AppState()
    monkeypatch.setattr(lb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def _voeg_les_toe(state) -> str:
    les = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    with state.doc.muteer("setup"):
        state.doc.project.lessen.append(les)
    return les.id


def _voeg_lesgever_toe(state, naam="Anne") -> str:
    lg = Lesgever(naam=naam)
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)
    return lg.id


def test_wijs_lesgever_toe(state):
    les_id = _voeg_les_toe(state)
    lg_id = _voeg_lesgever_toe(state)

    ok = lb.wijs_lesgever_toe(les_id, 0, lg_id)
    assert ok is True

    les = lb.vind_les(state.doc.project, les_id)
    assert len(les.toewijzingen) == 1
    assert les.toewijzingen[0].lesgever_id == lg_id
    assert les.toewijzingen[0].vast is True
    assert les.toewijzingen[0].bron == "handmatig"
    assert les.beschermd is True


def test_wijs_lesgever_toe_dubbel_wordt_geweigerd(state):
    les_id = _voeg_les_toe(state)
    lg_id = _voeg_lesgever_toe(state)
    lb.wijs_lesgever_toe(les_id, 0, lg_id)

    ok = lb.wijs_lesgever_toe(les_id, 1, lg_id)
    assert ok is False
    les = lb.vind_les(state.doc.project, les_id)
    assert len(les.toewijzingen) == 1
    assert not state.doc.kan_opnieuw()  # geen extra undo-entry aangemaakt


def test_wijs_lesgever_toe_vervangt_op_slot(state):
    les_id = _voeg_les_toe(state)
    lg1 = _voeg_lesgever_toe(state, "Anne")
    lg2 = _voeg_lesgever_toe(state, "Bob")
    lb.wijs_lesgever_toe(les_id, 0, lg1)
    lb.wijs_lesgever_toe(les_id, 0, lg2)

    les = lb.vind_les(state.doc.project, les_id)
    assert len(les.toewijzingen) == 1
    assert les.toewijzingen[0].lesgever_id == lg2


def test_wis_toewijzing(state):
    les_id = _voeg_les_toe(state)
    lg1 = _voeg_lesgever_toe(state, "Anne")
    lg2 = _voeg_lesgever_toe(state, "Bob")
    lb.wijs_lesgever_toe(les_id, 0, lg1)
    lb.wijs_lesgever_toe(les_id, 1, lg2)

    lb.wis_toewijzing(les_id, 0)
    les = lb.vind_les(state.doc.project, les_id)
    assert len(les.toewijzingen) == 1
    assert les.toewijzingen[0].lesgever_id == lg2  # opgeschoven


def test_wissel_vast(state):
    les_id = _voeg_les_toe(state)
    lg = _voeg_lesgever_toe(state)
    lb.wijs_lesgever_toe(les_id, 0, lg)
    les = lb.vind_les(state.doc.project, les_id)
    assert les.toewijzingen[0].vast is True

    lb.wissel_vast(les_id, 0)
    les = lb.vind_les(state.doc.project, les_id)
    assert les.toewijzingen[0].vast is False


def test_markeer_vervallen_wist_toewijzingen(state):
    les_id = _voeg_les_toe(state)
    lg = _voeg_lesgever_toe(state)
    lb.wijs_lesgever_toe(les_id, 0, lg)

    lb.markeer_vervallen(les_id, "Beka")
    les = lb.vind_les(state.doc.project, les_id)
    assert les.status == "vervallen"
    assert les.vervallen_reden == "Beka"
    assert les.toewijzingen == []


def test_markeer_gaat_weer_door(state):
    les_id = _voeg_les_toe(state)
    lb.markeer_vervallen(les_id, "Beka")
    lb.markeer_gaat_weer_door(les_id)
    les = lb.vind_les(state.doc.project, les_id)
    assert les.status == "gaat_door"
    assert les.vervallen_reden is None


def test_wijzig_tijd_en_titel(state):
    les_id = _voeg_les_toe(state)
    lb.wijzig_tijd(les_id, time(10, 0), time(12, 0))
    lb.wijzig_titel(les_id, "Open Les")
    les = lb.vind_les(state.doc.project, les_id)
    assert les.begin_tijd == time(10, 0)
    assert les.eind_tijd == time(12, 0)
    assert les.titel == "Open Les"
    assert les.beschermd is True


def test_verwijder_extra_les_alleen_bij_soort_extra(state):
    regulier_id = _voeg_les_toe(state)
    assert lb.verwijder_extra_les(regulier_id) is False
    assert lb.vind_les(state.doc.project, regulier_id) is not None

    extra_id = lb.voeg_extra_les_toe(date(2026, 4, 25), time(10, 0), time(12, 0), "Open Les")
    assert lb.verwijder_extra_les(extra_id) is True
    assert lb.vind_les(state.doc.project, extra_id) is None


def test_aantal_lessen_voor_telt_alleen_doorgaande_lessen(state):
    lg = _voeg_lesgever_toe(state)
    les1 = _voeg_les_toe(state)
    les2_id = lb.voeg_extra_les_toe(date(2026, 4, 25), time(10, 0), time(12, 0), "X")
    lb.wijs_lesgever_toe(les1, 0, lg)
    lb.wijs_lesgever_toe(les2_id, 0, lg)
    lb.markeer_vervallen(les2_id, "Afgelast")

    assert lb.aantal_lessen_voor(state.doc.project, lg) == 1


def test_pas_solverresultaat_toe_behoudt_vaste_toewijzingen(state):
    les_id = _voeg_les_toe(state)
    anne = _voeg_lesgever_toe(state, "Anne")
    bob = _voeg_lesgever_toe(state, "Bob")
    # Anne staat al vast (bv. handmatig ingedeeld voordat de solver draaide).
    lb.wijs_lesgever_toe(les_id, 0, anne)

    lb.pas_solverresultaat_toe({les_id}, {les_id: [anne, bob]})

    les = lb.vind_les(state.doc.project, les_id)
    namen_vast = {tw.lesgever_id: tw.vast for tw in les.toewijzingen}
    bronnen = {tw.lesgever_id: tw.bron for tw in les.toewijzingen}
    assert namen_vast == {anne: True, bob: False}
    assert bronnen == {anne: "handmatig", bob: "solver"}


def test_pas_solverresultaat_toe_raakt_niet_aangevinkte_lessen_niet_aan(state):
    les1 = _voeg_les_toe(state)
    les2 = lb.voeg_extra_les_toe(date(2026, 4, 25), time(10, 0), time(12, 0), "X")
    lg = _voeg_lesgever_toe(state)

    lb.pas_solverresultaat_toe({les1}, {les1: [lg], les2: [lg]})

    assert lb.vind_les(state.doc.project, les1).toewijzingen[0].lesgever_id == lg
    assert lb.vind_les(state.doc.project, les2).toewijzingen == []


def test_pas_solverresultaat_toe_vervangt_niet_vaste_toewijzing(state):
    les_id = _voeg_les_toe(state)
    anne = _voeg_lesgever_toe(state, "Anne")
    bob = _voeg_lesgever_toe(state, "Bob")
    lb.wijs_lesgever_toe(les_id, 0, anne)
    lb.wissel_vast(les_id, 0)  # Anne staat er niet-vast (bv. eerder solvervoorstel)

    lb.pas_solverresultaat_toe({les_id}, {les_id: [bob]})

    les = lb.vind_les(state.doc.project, les_id)
    assert [tw.lesgever_id for tw in les.toewijzingen] == [bob]
    assert les.toewijzingen[0].bron == "solver"
