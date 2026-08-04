from datetime import date, time

from lesgeefplanner.domain.calendar import (
    bereken_kalender_diff,
    gewenste_lessen,
    pas_kalender_diff_toe,
)
from lesgeefplanner.model import Project, Seizoen, Toewijzing, WeekSlot
from lesgeefplanner.model.entities import Herkomst, Les


def _basis_project() -> Project:
    return Project(
        naam="Test",
        weekrooster=[
            WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0)),  # woensdag
            WeekSlot(dag=5, begin_tijd=time(14, 0), eind_tijd=time(17, 0)),  # zaterdag
        ],
    )


def test_gewenste_lessen_eenvoudig_seizoen():
    project = _basis_project()
    project.seizoenen.append(
        Seizoen(naam="Voorseizoen 1", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    )
    gewenst = gewenste_lessen(project)
    datums = sorted(gw.datum for gw in gewenst.values())
    # 19 april is een zondag; het seizoen begint dus midden in een week.
    # Woensdagen: 22, 29 apr, 6 mei. Zaterdagen: 25 apr, 2, 9 mei.
    assert datums == [
        date(2026, 4, 22), date(2026, 4, 25), date(2026, 4, 29),
        date(2026, 5, 2), date(2026, 5, 6), date(2026, 5, 9),
    ]


def test_gewenste_lessen_lege_weekrooster_is_geen_lessen():
    """Regressietest: `if seizoen.weekrooster:` zou hier fout gaan, want [] is falsy maar
    betekent hier 'bewust geen lessen', niet 'gebruik het jaarrooster'."""
    project = _basis_project()
    project.seizoenen.append(
        Seizoen(naam="PKursus", begin=date(2026, 3, 16), eind=date(2026, 4, 19), weekrooster=[])
    )
    gewenst = gewenste_lessen(project)
    assert gewenst == {}


def test_gewenste_lessen_grens_op_precies_begin_en_eind():
    project = Project(naam="Test", weekrooster=[
        WeekSlot(dag=0, begin_tijd=time(10, 0), eind_tijd=time(12, 0)),  # maandag
    ])
    # Begin op een maandag, eind op de zondag van de volgende week: 2 maandagen.
    project.seizoenen.append(
        Seizoen(naam="S", begin=date(2026, 4, 20), eind=date(2026, 4, 26))
    )
    gewenst = gewenste_lessen(project)
    assert sorted(gw.datum for gw in gewenst.values()) == [date(2026, 4, 20)]


def test_gewenste_lessen_overlappende_seizoenen_eerste_wint():
    project = Project(naam="Test", weekrooster=[
        WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0)),
    ])
    s1 = Seizoen(naam="Eerst", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    s2 = Seizoen(naam="Tweede", begin=date(2026, 5, 1), eind=date(2026, 5, 20))
    project.seizoenen.extend([s1, s2])

    gewenst = gewenste_lessen(project)
    # 6 mei valt in beide seizoenen; moet aan s1 zijn toegekend.
    sleutels_op_6_mei = [s for s in gewenst if s[1] == date(2026, 5, 6)]
    assert len(sleutels_op_6_mei) == 1
    assert sleutels_op_6_mei[0][0] == s1.id


def test_diff_leeg_als_alles_al_bestaat():
    project = _basis_project()
    project.seizoenen.append(
        Seizoen(naam="S", begin=date(2026, 4, 22), eind=date(2026, 4, 22))
    )
    diff = bereken_kalender_diff(project)
    assert not diff.is_leeg()  # nog niets gematerialiseerd
    geaccepteerd = {les.id for les in diff.toe_te_voegen}
    with_ids = geaccepteerd
    pas_kalender_diff_toe(project, diff, with_ids)

    diff2 = bereken_kalender_diff(project)
    assert diff2.is_leeg()


def test_diff_beschermde_les_gaat_naar_conflicten_niet_verwijderen():
    project = _basis_project()
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 22), eind=date(2026, 4, 22))
    project.seizoenen.append(seizoen)

    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen.id, herkomst=Herkomst(seizoen_id=seizoen.id, weekslot_index=0),
        beschermd=True, titel="Aangepast",
    )
    project.lessen.append(les)

    # Verwijder het seizoen zodat deze les niet meer gewenst is.
    project.seizoenen.clear()
    diff = bereken_kalender_diff(project)
    assert diff.te_verwijderen == []
    assert len(diff.conflicten) == 1
    assert diff.conflicten[0][0].id == les.id


def test_diff_les_met_toewijzingen_gaat_naar_conflicten():
    project = _basis_project()
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 22), eind=date(2026, 4, 22))
    project.seizoenen.append(seizoen)
    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen.id, herkomst=Herkomst(seizoen_id=seizoen.id, weekslot_index=0),
        toewijzingen=[Toewijzing(lesgever_id="x", vast=True)],
    )
    project.lessen.append(les)
    project.seizoenen.clear()

    diff = bereken_kalender_diff(project)
    assert diff.te_verwijderen == []
    assert len(diff.conflicten) == 1


def test_diff_ongewijzigde_onbeschermde_les_gaat_naar_verwijderen():
    project = _basis_project()
    seizoen = Seizoen(naam="S", begin=date(2026, 4, 22), eind=date(2026, 4, 22))
    project.seizoenen.append(seizoen)
    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen.id, herkomst=Herkomst(seizoen_id=seizoen.id, weekslot_index=0),
    )
    project.lessen.append(les)
    project.seizoenen.clear()

    diff = bereken_kalender_diff(project)
    assert len(diff.te_verwijderen) == 1
    assert diff.conflicten == []


def test_diff_niet_toegepast_zonder_acceptatie():
    project = _basis_project()
    project.seizoenen.append(
        Seizoen(naam="S", begin=date(2026, 4, 22), eind=date(2026, 4, 22))
    )
    diff = bereken_kalender_diff(project)
    pas_kalender_diff_toe(project, diff, geaccepteerd=set())
    assert project.lessen == []


def test_extra_les_nooit_geraakt_door_diff():
    project = _basis_project()
    extra = Les(datum=date(2026, 4, 22), begin_tijd=time(10, 0), eind_tijd=time(12, 0),
                soort="extra", titel="Open Les")
    project.lessen.append(extra)
    diff = bereken_kalender_diff(project)
    assert diff.te_verwijderen == []
    assert diff.conflicten == []
    assert project.lessen == [extra]
