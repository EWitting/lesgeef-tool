from datetime import datetime

from lesgeefplanner.domain.beschikbaarheid import niet_meedoende_lesgevers
from lesgeefplanner.model import Project, Scope
from lesgeefplanner.model.availability import Antwoord, Ronde, RondeVraag


def _ronde(naam: str, aangemaakt_op: datetime, les_id: str, antwoorden: list[Antwoord]) -> Ronde:
    return Ronde(
        naam=naam,
        aangemaakt_op=aangemaakt_op,
        scope=Scope(),
        vragen=[RondeVraag(index=1, les_id=les_id, label="Les 1")],
        antwoorden=antwoorden,
    )


def test_doet_mee_false_telt_als_niet_meedoend():
    project = Project(naam="T")
    project.rondes = [
        _ronde("R1", datetime(2026, 1, 1), "les1", [Antwoord(lesgever_id="lg1", doet_mee=False)]),
    ]
    assert niet_meedoende_lesgevers(project, {"les1"}) == {"lg1"}


def test_doet_mee_true_telt_niet_mee():
    project = Project(naam="T")
    project.rondes = [
        _ronde("R1", datetime(2026, 1, 1), "les1", [Antwoord(lesgever_id="lg1", doet_mee=True)]),
    ]
    assert niet_meedoende_lesgevers(project, {"les1"}) == set()


def test_ronde_buiten_les_ids_telt_niet_mee():
    """Iemand die 'nee' zei op een ronde die niets met de gevraagde lessen te maken heeft,
    mag niet als afwezig voor DEZE periode getoond worden."""
    project = Project(naam="T")
    project.rondes = [
        _ronde("R1", datetime(2026, 1, 1), "andere_les", [Antwoord(lesgever_id="lg1", doet_mee=False)]),
    ]
    assert niet_meedoende_lesgevers(project, {"les1"}) == set()


def test_nieuwste_relevante_ronde_wint():
    project = Project(naam="T")
    project.rondes = [
        _ronde("Oud", datetime(2026, 1, 1), "les1", [Antwoord(lesgever_id="lg1", doet_mee=False)]),
        _ronde("Nieuw", datetime(2026, 2, 1), "les1", [Antwoord(lesgever_id="lg1", doet_mee=True)]),
    ]
    assert niet_meedoende_lesgevers(project, {"les1"}) == set()
