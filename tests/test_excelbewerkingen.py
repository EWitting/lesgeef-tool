from datetime import date, time

import pytest

from lesgeefplanner.exchange.types import Wijziging
from lesgeefplanner.model import Lesgever
from lesgeefplanner.model.entities import Les, Toewijzing
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import excelbewerkingen as eb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    st = AppState()
    monkeypatch.setattr(eb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def _voeg_les_toe(state) -> str:
    les = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    with state.doc.muteer("setup"):
        state.doc.project.lessen.append(les)
    return les.id


def test_toegevoegd(state):
    les_id = _voeg_les_toe(state)
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    aantal = eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="toegevoegd", lesgever_id=lg.id, oud="", nieuw="Anne")]
    )
    assert aantal == 1
    les = state.doc.project.lessen[0]
    assert les.toewijzingen[0].lesgever_id == lg.id
    assert les.toewijzingen[0].vast is True
    assert les.toewijzingen[0].bron == "import"
    assert les.beschermd is True


def test_verwijderd(state):
    les_id = _voeg_les_toe(state)
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)
        state.doc.project.lessen[0].toewijzingen.append(
            Toewijzing(lesgever_id=lg.id, vast=True)
        )

    eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="verwijderd", lesgever_id=lg.id, oud="Anne", nieuw="")]
    )
    assert state.doc.project.lessen[0].toewijzingen == []


def test_status_vervallen_met_reden(state):
    les_id = _voeg_les_toe(state)
    eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="status", lesgever_id=None, oud="Gaat door", nieuw="Vervalt — Beka")]
    )
    les = state.doc.project.lessen[0]
    assert les.status == "vervallen"
    assert les.vervallen_reden == "Beka"


def test_status_gaat_weer_door(state):
    les_id = _voeg_les_toe(state)
    with state.doc.muteer("setup"):
        state.doc.project.lessen[0].status = "vervallen"
        state.doc.project.lessen[0].vervallen_reden = "Beka"

    eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="status", lesgever_id=None, oud="Vervalt — Beka", nieuw="Gaat door")]
    )
    les = state.doc.project.lessen[0]
    assert les.status == "gaat_door"
    assert les.vervallen_reden is None


def test_titel(state):
    les_id = _voeg_les_toe(state)
    eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="titel", lesgever_id=None, oud="", nieuw="Open Les")]
    )
    assert state.doc.project.lessen[0].titel == "Open Les"


def test_geen_dubbele_toewijzing(state):
    les_id = _voeg_les_toe(state)
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)
        state.doc.project.lessen[0].toewijzingen.append(
            Toewijzing(lesgever_id=lg.id, vast=True)
        )

    eb.pas_wijzigingen_toe(
        [Wijziging(les_id=les_id, soort="toegevoegd", lesgever_id=lg.id, oud="", nieuw="Anne")]
    )
    assert len(state.doc.project.lessen[0].toewijzingen) == 1
