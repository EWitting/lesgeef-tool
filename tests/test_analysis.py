"""Elk van de 12 bevindingscodes uit docs/DESIGN.md §5 moet met een testproject op te
roepen zijn (docs/PLAN.md fase 5 acceptatiecriterium)."""
from datetime import date, datetime, time

from lesgeefplanner.domain.analysis import analyseer
from lesgeefplanner.domain.report import genereer_tekstrapport
from lesgeefplanner.model import Antwoord, Lesgever, Project, Ronde, RondeVraag, Scope, Seizoen
from lesgeefplanner.model.entities import Les, Toewijzing

PEILDATUM = date(2026, 1, 1)  # alles in de tests ligt "in de toekomst"


def _les(datum, seizoen_id=None, toewijzingen=None, status="gaat_door"):
    return Les(
        datum=datum, begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen_id, toewijzingen=toewijzingen or [], status=status,
    )


def _codes(bevindingen) -> set[str]:
    return {b.code for b in bevindingen}


def test_les_niet_ingevuld():
    project = Project(naam="T")
    project.lessen = [_les(date(2026, 4, 22))]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_niet_ingevuld" in _codes(bevindingen)


def test_les_te_weinig_lesgevers():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne")
    project.lesgevers = [lg]
    project.solver_config.lesgever_minimum = 2
    project.lessen = [_les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)])]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_te_weinig_lesgevers" in _codes(bevindingen)


def test_les_geen_ervaren_lesgever():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne", ervaring_jaren=0)
    project.lesgevers = [lg]
    project.solver_config.lesgever_minimum = 1
    project.lessen = [_les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)])]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_geen_ervaren_lesgever" in _codes(bevindingen)


def test_les_misschien_gebruikt():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne")
    project.lesgevers = [lg]
    les = _les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)])
    project.lessen = [les]
    project.rondes = [
        Ronde(
            naam="R1", aangemaakt_op=datetime(2026, 1, 1),
            scope=Scope(), vragen=[RondeVraag(index=1, les_id=les.id, label="L")],
            antwoorden=[Antwoord(lesgever_id=lg.id, waarden={les.id: "misschien"})],
        )
    ]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_misschien_gebruikt" in _codes(bevindingen)


def test_les_zonder_beschikbaarheid():
    project = Project(naam="T")
    project.lessen = [_les(date(2026, 4, 22))]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_zonder_beschikbaarheid" in _codes(bevindingen)


def test_lesgever_dubbel_in_week():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne")
    project.lesgevers = [lg]
    project.lessen = [
        _les(date(2026, 4, 20), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)]),
        _les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)]),
    ]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "lesgever_dubbel_in_week" in _codes(bevindingen)


def test_lesgever_boven_en_onder_richtlijn():
    project = Project(naam="T")
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 1), eind=date(2026, 5, 31))
    project.seizoenen = [seizoen]
    boven = Lesgever(naam="Boven")
    onder = Lesgever(naam="Onder")
    project.lesgevers = [boven, onder]
    project.solver_config.richtlijn_lessen_per_week = 0.0  # doel wordt max(1, 0) = 1
    project.lessen = [
        _les(date(2026, 4, 22), seizoen.id, [Toewijzing(lesgever_id=boven.id, vast=True)]),
        _les(date(2026, 4, 29), seizoen.id, [Toewijzing(lesgever_id=boven.id, vast=True)]),
        # 'onder' krijgt 0 lessen dit seizoen -> onder de richtlijn van 1
    ]
    bevindingen = analyseer(project, Scope(seizoen_ids=[seizoen.id], alleen_toekomst=False), PEILDATUM)
    codes = _codes(bevindingen)
    assert "lesgever_boven_richtlijn" in codes
    assert "lesgever_onder_richtlijn" in codes


def test_lesgever_niet_gereageerd():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne")
    project.lesgevers = [lg]
    les = _les(date(2026, 4, 22))
    project.lessen = [les]
    project.rondes = [
        Ronde(
            naam="R1", aangemaakt_op=datetime(2026, 1, 1),
            scope=Scope(), vragen=[RondeVraag(index=1, les_id=les.id, label="L")],
            antwoorden=[],
        )
    ]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "lesgever_niet_gereageerd" in _codes(bevindingen)


def test_lesgever_ingedeeld_maar_nee():
    project = Project(naam="T")
    lg = Lesgever(naam="Anne")
    project.lesgevers = [lg]
    les = _les(date(2026, 4, 22), toewijzingen=[Toewijzing(lesgever_id=lg.id, vast=True)])
    project.lessen = [les]
    project.rondes = [
        Ronde(
            naam="R1", aangemaakt_op=datetime(2026, 1, 1),
            scope=Scope(), vragen=[RondeVraag(index=1, les_id=les.id, label="L")],
            antwoorden=[Antwoord(lesgever_id=lg.id, waarden={les.id: "nee"})],
        )
    ]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "lesgever_ingedeeld_maar_nee" in _codes(bevindingen)


def test_seizoenen_overlappen():
    project = Project(naam="T")
    project.seizoenen = [
        Seizoen(naam="S1", begin=date(2026, 4, 1), eind=date(2026, 5, 15)),
        Seizoen(naam="S2", begin=date(2026, 5, 1), eind=date(2026, 6, 30)),
    ]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "seizoenen_overlappen" in _codes(bevindingen)


def test_les_buiten_seizoen():
    project = Project(naam="T")
    project.lessen = [_les(date(2026, 4, 22), seizoen_id=None)]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert "les_buiten_seizoen" in _codes(bevindingen)


def test_vervallen_les_geeft_geen_bevindingen():
    project = Project(naam="T")
    project.lessen = [_les(date(2026, 4, 22), status="vervallen")]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert bevindingen == []


def test_geen_bevindingen_bij_schoon_project():
    project = Project(naam="T")
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    assert bevindingen == []


def test_rapport_groepeert_op_ernst():
    project = Project(naam="T")
    project.lessen = [_les(date(2026, 4, 22))]
    bevindingen = analyseer(project, Scope(alleen_toekomst=False), PEILDATUM)
    tekst = genereer_tekstrapport(bevindingen)
    assert "FOUTEN" in tekst
    assert "niet ingevuld" in tekst


def test_rapport_leeg_project():
    assert genereer_tekstrapport([]) == "Geen bijzonderheden gevonden."
