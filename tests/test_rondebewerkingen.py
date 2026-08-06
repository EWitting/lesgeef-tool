from datetime import date, datetime, time, timedelta

import pytest

from lesgeefplanner.exchange.types import GekoppeldAntwoord, ImportResultaat, NaamProbleem
from lesgeefplanner.model import Lesgever, Scope
from lesgeefplanner.model.entities import Les
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import rondebewerkingen as rb
from lesgeefplanner.ui.state import AppState


@pytest.fixture()
def state(monkeypatch):
    st = AppState()
    monkeypatch.setattr(rb, "state", st)
    st.doc = Document.nieuw("Test")
    return st


def _voeg_lessen_toe(state, n=3) -> list[str]:
    ids = []
    with state.doc.muteer("setup"):
        for i in range(n):
            les = Les(
                datum=date(2026, 4, 20) + timedelta(days=7 * i),
                begin_tijd=time(16, 0), eind_tijd=time(19, 0),
            )
            state.doc.project.lessen.append(les)
            ids.append(les.id)
    return ids


def test_maak_ronde_genereert_vraag_per_les(state):
    les_ids = _voeg_lessen_toe(state, 3)
    ronde_id = rb.maak_ronde("Voorseizoen 1", Scope(alleen_toekomst=False), date(2026, 1, 1))

    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert len(ronde.vragen) == 3
    assert {v.les_id for v in ronde.vragen} == set(les_ids)
    assert [v.index for v in ronde.vragen] == [1, 2, 3]
    # Gesorteerd op datum
    assert ronde.vragen[0].les_id == les_ids[0]


def test_maak_ronde_respecteert_scope(state):
    _voeg_lessen_toe(state, 3)
    scope = Scope(van=date(2026, 4, 25), alleen_toekomst=False)
    ronde_id = rb.maak_ronde("Ronde", scope, date(2026, 1, 1))
    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert len(ronde.vragen) == 2  # les op 20 apr valt eraf


def test_verwerk_importresultaat_gekoppelde_antwoorden(state):
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    resultaat = ImportResultaat(
        ronde_id=ronde_id,
        gekoppelde_antwoorden=[
            GekoppeldAntwoord(lesgever_id=lg.id, waarden={les_ids[0]: "ja"}, ingevuld_op=datetime(2026, 1, 1))
        ],
    )
    aantal = rb.verwerk_importresultaat(resultaat, {})
    assert aantal == 1

    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert len(ronde.antwoorden) == 1
    assert ronde.antwoorden[0].waarden == {les_ids[0]: "ja"}


def test_verwerk_importresultaat_opgeloste_naamproblemen(state):
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    resultaat = ImportResultaat(
        ronde_id=ronde_id,
        naamproblemen=[
            NaamProbleem(ruwe_naam="Anne T.", voorstellen=[(lg.id, 0.8)], waarden={les_ids[0]: "misschien"})
        ],
    )
    aantal = rb.verwerk_importresultaat(resultaat, {"Anne T.": lg.id})
    assert aantal == 1
    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert ronde.antwoorden[0].lesgever_id == lg.id
    assert ronde.antwoorden[0].waarden == {les_ids[0]: "misschien"}


def test_verwerk_importresultaat_leert_alias_van_opgelost_naamprobleem(state):
    """Een handmatig opgeloste naam moet als alias op de lesgever blijven staan, zodat een
    volgende herupload met dezelfde afwijkende spelling niet opnieuw de wizard toont."""
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    resultaat = ImportResultaat(
        ronde_id=ronde_id,
        naamproblemen=[
            NaamProbleem(ruwe_naam="Anne T.", voorstellen=[(lg.id, 0.8)], waarden={les_ids[0]: "ja"})
        ],
    )
    rb.verwerk_importresultaat(resultaat, {"Anne T.": lg.id})

    lesgever = next(l for l in state.doc.project.lesgevers if l.id == lg.id)
    assert lesgever.aliassen == ["Anne T."]


def test_verwerk_importresultaat_overgeslagen_naamprobleem_leert_geen_alias(state):
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    resultaat = ImportResultaat(
        ronde_id=ronde_id,
        naamproblemen=[NaamProbleem(ruwe_naam="Iemand Anders", waarden={les_ids[0]: "ja"})],
    )
    rb.verwerk_importresultaat(resultaat, {"Iemand Anders": None})

    lesgever = next(l for l in state.doc.project.lesgevers if l.id == lg.id)
    assert lesgever.aliassen == []


def test_verwerk_importresultaat_overgeslagen_naamprobleem_telt_niet_mee(state):
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))

    resultaat = ImportResultaat(
        ronde_id=ronde_id,
        naamproblemen=[NaamProbleem(ruwe_naam="Onbekend", waarden={les_ids[0]: "ja"})],
    )
    aantal = rb.verwerk_importresultaat(resultaat, {"Onbekend": None})
    assert aantal == 0
    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert ronde.antwoorden == []


def test_verwerk_importresultaat_vervangt_bestaand_antwoord(state):
    les_ids = _voeg_lessen_toe(state, 1)
    ronde_id = rb.maak_ronde("R", Scope(alleen_toekomst=False), date(2026, 1, 1))
    lg = Lesgever(naam="Anne")
    with state.doc.muteer("setup"):
        state.doc.project.lesgevers.append(lg)

    eerste = ImportResultaat(
        ronde_id=ronde_id,
        gekoppelde_antwoorden=[GekoppeldAntwoord(lesgever_id=lg.id, waarden={les_ids[0]: "ja"})],
    )
    rb.verwerk_importresultaat(eerste, {})

    tweede = ImportResultaat(
        ronde_id=ronde_id,
        gekoppelde_antwoorden=[GekoppeldAntwoord(lesgever_id=lg.id, waarden={les_ids[0]: "nee"})],
    )
    rb.verwerk_importresultaat(tweede, {})

    ronde = next(r for r in state.doc.project.rondes if r.id == ronde_id)
    assert len(ronde.antwoorden) == 1
    assert ronde.antwoorden[0].waarden == {les_ids[0]: "nee"}
