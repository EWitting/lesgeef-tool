from datetime import date, datetime, time

from lesgeefplanner.model import Antwoord, Lesgever, Project, Ronde, Scope, Seizoen
from lesgeefplanner.model.entities import Les
from lesgeefplanner.planner.request import bouw_request


def test_scope_splitsing_context_bevat_verleden_zelfde_seizoen():
    project = Project(naam="T")
    s1 = Seizoen(naam="S1", begin=date(2026, 4, 1), eind=date(2026, 6, 30))
    s2 = Seizoen(naam="S2", begin=date(2026, 7, 1), eind=date(2026, 9, 30))
    project.seizoenen = [s1, s2]

    verleden_zelfde_seizoen = Les(
        datum=date(2026, 4, 10), begin_tijd=time(16, 0), eind_tijd=time(19, 0), seizoen_id=s1.id
    )
    toekomst_zelfde_seizoen = Les(
        datum=date(2026, 5, 10), begin_tijd=time(16, 0), eind_tijd=time(19, 0), seizoen_id=s1.id
    )
    ander_seizoen = Les(
        datum=date(2026, 8, 10), begin_tijd=time(16, 0), eind_tijd=time(19, 0), seizoen_id=s2.id
    )
    vervallen_zelfde_seizoen = Les(
        datum=date(2026, 5, 15), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=s1.id, status="vervallen",
    )
    project.lessen = [
        verleden_zelfde_seizoen, toekomst_zelfde_seizoen, ander_seizoen, vervallen_zelfde_seizoen,
    ]

    scope = Scope(seizoen_ids=[s1.id], alleen_toekomst=True)
    peildatum = date(2026, 4, 15)

    request = bouw_request(project, scope, peildatum)

    assert request.lessen_in_scope == [toekomst_zelfde_seizoen]
    assert request.lessen_context == [verleden_zelfde_seizoen]
    assert ander_seizoen not in request.lessen_context
    assert vervallen_zelfde_seizoen not in request.lessen_in_scope
    assert vervallen_zelfde_seizoen not in request.lessen_context


def test_alleen_actieve_lesgevers():
    project = Project(naam="T")
    project.lesgevers = [
        Lesgever(naam="Actief", actief=True),
        Lesgever(naam="Inactief", actief=False),
    ]
    request = bouw_request(project, Scope(alleen_toekomst=False), date(2026, 1, 1))
    namen = {lg.naam for lg in request.lesgevers}
    assert namen == {"Actief"}


def test_beschikbaarheid_nieuwste_ronde_wint():
    project = Project(naam="T")
    les = Les(datum=date(2026, 5, 1), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    project.lessen = [les]
    lg = Lesgever(naam="A")
    project.lesgevers = [lg]

    ronde_oud = Ronde(
        naam="R1", aangemaakt_op=datetime(2026, 1, 1), scope=Scope(),
        antwoorden=[Antwoord(lesgever_id=lg.id, waarden={les.id: "nee"})],
    )
    ronde_nieuw = Ronde(
        naam="R2", aangemaakt_op=datetime(2026, 2, 1), scope=Scope(),
        antwoorden=[Antwoord(lesgever_id=lg.id, waarden={les.id: "ja"})],
    )
    project.rondes = [ronde_oud, ronde_nieuw]

    request = bouw_request(project, Scope(alleen_toekomst=False), date(2026, 1, 1))
    assert request.beschikbaarheid[(lg.id, les.id)] == "ja"


def test_beschikbaarheid_doet_mee_false_genegeerd():
    project = Project(naam="T")
    les = Les(datum=date(2026, 5, 1), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    project.lessen = [les]
    lg = Lesgever(naam="A")
    project.lesgevers = [lg]

    ronde = Ronde(
        naam="R1", aangemaakt_op=datetime(2026, 1, 1), scope=Scope(),
        antwoorden=[Antwoord(lesgever_id=lg.id, doet_mee=False, waarden={les.id: "ja"})],
    )
    project.rondes = [ronde]

    request = bouw_request(project, Scope(alleen_toekomst=False), date(2026, 1, 1))
    assert (lg.id, les.id) not in request.beschikbaarheid
