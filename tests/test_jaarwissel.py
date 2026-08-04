from datetime import date, time, timedelta

from lesgeefplanner.domain.jaarwissel import rol_project_door
from lesgeefplanner.model import Lesgever, Project, Seizoen, WeekSlot
from lesgeefplanner.model.entities import Herkomst, Les, Toewijzing


def test_lesgevers_blijven_met_plus_een_jaar_ervaring():
    oud = Project(naam="Oud")
    lg = Lesgever(naam="Anne", ervaring_jaren=2, actief=True)
    oud.lesgevers = [lg]

    nieuw = rol_project_door(oud, "Nieuw")
    assert len(nieuw.lesgevers) == 1
    assert nieuw.lesgevers[0].id == lg.id  # zelfde persoon, zelfde id
    assert nieuw.lesgevers[0].ervaring_jaren == 3
    assert nieuw.lesgevers[0].naam == "Anne"


def test_seizoenen_schuiven_op_met_364_dagen():
    oud = Project(naam="Oud")
    seizoen = Seizoen(naam="Voorseizoen 1", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    oud.seizoenen = [seizoen]

    nieuw = rol_project_door(oud, "Nieuw")
    assert len(nieuw.seizoenen) == 1
    nieuw_seizoen = nieuw.seizoenen[0]
    assert nieuw_seizoen.naam == "Voorseizoen 1"
    assert nieuw_seizoen.begin == date(2026, 4, 19) + timedelta(days=364)
    # Zelfde weekdag behouden (364 = 52 weken)
    assert nieuw_seizoen.begin.weekday() == seizoen.begin.weekday()
    assert nieuw_seizoen.id != seizoen.id


def test_reguliere_lessen_worden_niet_meegenomen():
    oud = Project(naam="Oud")
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    oud.seizoenen = [seizoen]
    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen.id, herkomst=Herkomst(seizoen_id=seizoen.id, weekslot_index=0),
        toewijzingen=[Toewijzing(lesgever_id="x", vast=True)],
    )
    oud.lessen = [les]

    nieuw = rol_project_door(oud, "Nieuw")
    assert nieuw.lessen == []


def test_extra_lessen_blijven_met_opgeschoven_datum_en_zonder_toewijzingen():
    oud = Project(naam="Oud")
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    oud.seizoenen = [seizoen]
    extra = Les(
        datum=date(2026, 4, 25), begin_tijd=time(10, 0), eind_tijd=time(12, 0),
        seizoen_id=seizoen.id, titel="Open Les", soort="extra",
        toewijzingen=[Toewijzing(lesgever_id="x", vast=True)],
    )
    oud.lessen = [extra]

    nieuw = rol_project_door(oud, "Nieuw")
    assert len(nieuw.lessen) == 1
    nieuwe_extra = nieuw.lessen[0]
    assert nieuwe_extra.datum == date(2026, 4, 25) + timedelta(days=364)
    assert nieuwe_extra.titel == "Open Les"
    assert nieuwe_extra.toewijzingen == []
    assert nieuwe_extra.seizoen_id == nieuw.seizoenen[0].id


def test_weekrooster_en_solver_config_gekopieerd():
    oud = Project(naam="Oud")
    oud.weekrooster = [WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0))]
    oud.solver_config.lesgever_minimum = 5

    nieuw = rol_project_door(oud, "Nieuw")
    assert nieuw.weekrooster == oud.weekrooster
    assert nieuw.weekrooster is not oud.weekrooster
    assert nieuw.solver_config.lesgever_minimum == 5


def test_geen_rondes_of_werkblad_meegenomen():
    oud = Project(naam="Oud")
    oud.werkblad.laatste_export_pad = "C:/iets.xlsx"
    nieuw = rol_project_door(oud, "Nieuw")
    assert nieuw.rondes == []
    assert nieuw.werkblad.laatste_export_pad is None
