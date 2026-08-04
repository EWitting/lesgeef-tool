from datetime import date, datetime, time

from lesgeefplanner.model import Antwoord, Lesgever, Project, Ronde, RondeVraag, Scope, Seizoen
from lesgeefplanner.model.entities import Herkomst, Les, Toewijzing
from lesgeefplanner.ui import stappen

PEILDATUM = date(2026, 1, 1)


def test_stap_jaarplanning_leeg_zonder_seizoenen():
    project = Project(naam="T")
    assert stappen.stap_jaarplanning(project) == "leeg"


def test_stap_jaarplanning_aandacht_bij_niet_bijgewerkte_kalender():
    project = Project(naam="T")
    project.weekrooster = []
    project.seizoenen.append(Seizoen(naam="S", begin=date(2026, 4, 1), eind=date(2026, 4, 1)))
    # geen weekrooster -> gewenste_lessen is leeg -> aandacht
    assert stappen.stap_jaarplanning(project) == "aandacht"


def test_stap_lesgevers():
    project = Project(naam="T")
    assert stappen.stap_lesgevers(project) == "leeg"
    project.lesgevers.append(Lesgever(naam="Anne", actief=False))
    assert stappen.stap_lesgevers(project) == "aandacht"
    project.lesgevers.append(Lesgever(naam="Bob", actief=True))
    assert stappen.stap_lesgevers(project) == "klaar"


def test_stap_beschikbaarheid():
    project = Project(naam="T")
    assert stappen.stap_beschikbaarheid(project) == "leeg"
    project.rondes.append(Ronde(naam="R", aangemaakt_op=datetime(2026, 1, 1), scope=Scope()))
    assert stappen.stap_beschikbaarheid(project) == "aandacht"
    project.rondes[0].antwoorden.append(Antwoord(lesgever_id="x"))
    assert stappen.stap_beschikbaarheid(project) == "klaar"


def test_stap_inroosteren():
    project = Project(naam="T")
    assert stappen.stap_inroosteren(project, PEILDATUM) == "leeg"

    les = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    project.lessen.append(les)
    assert stappen.stap_inroosteren(project, PEILDATUM) == "aandacht"  # niet ingevuld = fout

    les.toewijzingen.append(Toewijzing(lesgever_id="x", vast=True))
    project.lesgevers.append(Lesgever(id="x", naam="Anne"))
    project.solver_config.lesgever_minimum = 1
    assert stappen.stap_inroosteren(project, PEILDATUM) == "klaar"


def test_stap_delen():
    project = Project(naam="T")
    assert stappen.stap_delen(project) == "leeg"
    project.werkblad.laatste_export_pad = "C:/ergens/planning.xlsx"
    assert stappen.stap_delen(project) == "klaar"


def test_alle_stappen_bevat_vijf_sleutels():
    project = Project(naam="T")
    resultaat = stappen.alle_stappen(project, PEILDATUM)
    assert set(resultaat.keys()) == {
        "Jaarplanning", "Lesgevers", "Beschikbaarheid", "Inroosteren", "Delen",
    }
