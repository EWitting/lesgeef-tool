"""Tests voor de solver zelf (docs/DESIGN.md §8): vaste toewijzingen, context-tellingen voor
weekconflict en werkverdeling, wijzigingskosten, dat verdeling optelt tot score, en
determinisme."""
from datetime import date, time

from lesgeefplanner.model import Lesgever
from lesgeefplanner.model.config import SolverConfig
from lesgeefplanner.model.entities import Les, Toewijzing
from lesgeefplanner.planner.request import PlanRequest
from lesgeefplanner.planner.solve import los_op


def _les(datum, seizoen_id=None, toewijzingen=None, status="gaat_door"):
    return Les(
        datum=datum, begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen_id, toewijzingen=toewijzingen or [], status=status,
    )


def test_vaste_toewijzing_blijft_staan_ondanks_nee():
    les = _les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id="A", vast=True)])
    lesgevers = [Lesgever(id="A", naam="A"), Lesgever(id="B", naam="B")]
    config = SolverConfig(lesgever_minimum=1, lesgever_maximum=2)
    request = PlanRequest(
        lessen_in_scope=[les], lessen_context=[], lesgevers=lesgevers,
        beschikbaarheid={("A", les.id): "nee", ("B", les.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.status in ("optimaal", "haalbaar")
    assert "A" in result.toewijzingen[les.id]


def test_week_conflict_telt_context_mee():
    seizoen_id = "s1"
    les_context = _les(
        date(2026, 4, 20), seizoen_id=seizoen_id,
        toewijzingen=[Toewijzing(lesgever_id="A", vast=True)],
    )
    les_scope = _les(
        date(2026, 4, 22), seizoen_id=seizoen_id,  # zelfde ISO-week als 20 april
        toewijzingen=[Toewijzing(lesgever_id="A", vast=True)],
    )
    config = SolverConfig(lesgever_minimum=1, lesgever_maximum=1)
    request = PlanRequest(
        lessen_in_scope=[les_scope], lessen_context=[les_context],
        lesgevers=[Lesgever(id="A", naam="A")],
        beschikbaarheid={("A", les_scope.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.verdeling.get("week_conflict", 0) > 0


def test_week_conflict_geen_penalty_zonder_context():
    seizoen_id = "s1"
    les_scope = _les(date(2026, 4, 22), seizoen_id=seizoen_id)
    config = SolverConfig(lesgever_minimum=1, lesgever_maximum=1)
    request = PlanRequest(
        lessen_in_scope=[les_scope], lessen_context=[],
        lesgevers=[Lesgever(id="A", naam="A")],
        beschikbaarheid={("A", les_scope.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.verdeling.get("week_conflict", 0) == 0


def test_werkverdeling_telt_reeds_gegeven_lessen_mee():
    seizoen_id = "s1"
    les_context = _les(
        date(2026, 4, 20), seizoen_id=seizoen_id,
        toewijzingen=[Toewijzing(lesgever_id="A", vast=True)],
    )
    les_scope = _les(date(2026, 5, 4), seizoen_id=seizoen_id)  # andere week
    config = SolverConfig(
        lesgever_minimum=1, lesgever_maximum=1, richtlijn_lessen_per_week=0.0,
        penalty_boven_richtlijn=4, penalty_verdeling_stappen=[1],
    )
    request = PlanRequest(
        lessen_in_scope=[les_scope], lessen_context=[les_context],
        lesgevers=[Lesgever(id="A", naam="A")],
        beschikbaarheid={("A", les_scope.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.verdeling.get("boven_richtlijn", 0) > 0


def test_werkverdeling_geen_penalty_zonder_context():
    seizoen_id = "s1"
    les_scope = _les(date(2026, 5, 4), seizoen_id=seizoen_id)
    config = SolverConfig(
        lesgever_minimum=1, lesgever_maximum=1, richtlijn_lessen_per_week=0.0,
        penalty_boven_richtlijn=4, penalty_verdeling_stappen=[1],
    )
    request = PlanRequest(
        lessen_in_scope=[les_scope], lessen_context=[],
        lesgevers=[Lesgever(id="A", naam="A")],
        beschikbaarheid={("A", les_scope.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.verdeling.get("boven_richtlijn", 0) == 0


def test_wijzigingskosten_voorkomt_onnodige_omgooi():
    les = _les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id="B", vast=False, bron="solver")])
    config = SolverConfig(lesgever_minimum=1, lesgever_maximum=1, penalty_wijziging=6)
    request = PlanRequest(
        lessen_in_scope=[les], lessen_context=[],
        lesgevers=[Lesgever(id="A", naam="A"), Lesgever(id="B", naam="B")],
        beschikbaarheid={("A", les.id): "ja", ("B", les.id): "ja"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.toewijzingen[les.id] == ["B"]


def test_verdeling_telt_op_tot_score():
    les = _les(date(2026, 4, 22))
    config = SolverConfig(lesgever_minimum=1, lesgever_maximum=2)
    request = PlanRequest(
        lessen_in_scope=[les], lessen_context=[],
        lesgevers=[Lesgever(id="A", naam="A"), Lesgever(id="B", naam="B")],
        beschikbaarheid={("A", les.id): "ja", ("B", les.id): "misschien"},
        config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert abs(sum(result.verdeling.values()) - result.score) < 1e-6


def test_onhaalbaar_bij_conflicterende_vaste_toewijzingen():
    les = _les(
        date(2026, 4, 22),
        toewijzingen=[
            Toewijzing(lesgever_id="A", vast=True),
            Toewijzing(lesgever_id="B", vast=True),
            Toewijzing(lesgever_id="C", vast=True),
        ],
    )
    lesgevers = [Lesgever(id=x, naam=x) for x in ("A", "B", "C")]
    config = SolverConfig(lesgever_maximum=1, lesgever_minimum=1)
    request = PlanRequest(
        lessen_in_scope=[les], lessen_context=[], lesgevers=lesgevers,
        beschikbaarheid={}, config=config, peildatum=date(2026, 4, 21),
    )
    result = los_op(request)
    assert result.status == "onhaalbaar"


def _scenario_klein() -> PlanRequest:
    """4 lessen, 5 lesgevers, gevarieerde beschikbaarheid -- voor determinisme-check."""
    lessen = [
        _les(date(2026, 4, 22)), _les(date(2026, 4, 29)),
        _les(date(2026, 5, 6)), _les(date(2026, 5, 13)),
    ]
    lesgevers = [Lesgever(id=f"lg{i}", naam=f"Lg{i}", ervaring_jaren=i % 2) for i in range(5)]
    beschikbaarheid = {}
    for i, lg in enumerate(lesgevers):
        for j, les in enumerate(lessen):
            waarde = ["ja", "misschien", "nee"][(i + j) % 3]
            beschikbaarheid[(lg.id, les.id)] = waarde
    return PlanRequest(
        lessen_in_scope=lessen, lessen_context=[], lesgevers=lesgevers,
        beschikbaarheid=beschikbaarheid, config=SolverConfig(), peildatum=date(2026, 4, 21),
    )


def test_determinisme():
    request = _scenario_klein()
    r1 = los_op(request)
    r2 = los_op(request)
    assert r1.toewijzingen == r2.toewijzingen
    assert r1.score == r2.score
