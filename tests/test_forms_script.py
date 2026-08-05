from datetime import date, datetime, time

from lesgeefplanner.exchange.forms_script import genereer_apps_script
from lesgeefplanner.model import Project, Ronde, RondeVraag, Scope
from lesgeefplanner.model.entities import Les


def _ronde_met_project() -> tuple[Ronde, Project]:
    project = Project(naam="T")
    les1 = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    les2 = Les(datum=date(2026, 6, 28), begin_tijd=time(14, 0), eind_tijd=time(17, 0))
    project.lessen = [les1, les2]
    ronde = Ronde(
        naam="R1", aangemaakt_op=datetime(2026, 1, 1), scope=Scope(),
        vragen=[
            RondeVraag(index=1, les_id=les1.id, label="woensdag 22 april 16:00 - 19:00"),
            RondeVraag(index=2, les_id=les2.id, label="zondag 28 juni 14:00 - 17:00"),
        ],
    )
    return ronde, project


def test_script_bevat_screeningvraag_met_vertakking():
    ronde, project = _ronde_met_project()
    script = genereer_apps_script(ronde, project)
    assert "addPageBreakItem" in script
    assert "FormApp.PageNavigationType.SUBMIT" in script


def test_script_gebruikt_rooster_niet_losse_vragen_per_les():
    ronde, project = _ronde_met_project()
    script = genereer_apps_script(ronde, project)
    assert "addGridItem" in script
    assert "addMultipleChoiceItem" in script  # alleen de screeningvraag
    assert script.count("addMultipleChoiceItem") == 1
    # Geen '#N'-suffix meer -- koppeling gebeurt op volgorde (zie forms_import.py).
    assert "woensdag 22 april 16:00 - 19:00" in script
    assert "zondag 28 juni 14:00 - 17:00" in script
    assert "#1" not in script
    assert "#2" not in script


def test_script_naamvraag_is_vrije_tekst():
    """Geen dropdown (setChoiceValues) meer -- een leeg/onvolledig lesgeverslijstje mag de
    naamvraag niet kunnen breken, en fuzzy-matching bij import vangt typefouten toch al op."""
    ronde, project = _ronde_met_project()
    script = genereer_apps_script(ronde, project)
    assert "addTextItem" in script
    assert "setChoiceValues" not in script


def test_screeningtekst_bevat_periode_van_eerste_tot_laatste_les():
    ronde, project = _ronde_met_project()
    script = genereer_apps_script(ronde, project)
    assert "22 april" in script
    assert "28 juni" in script


def test_beheerder_waarschuwing_staat_niet_in_setdescription():
    """De vroegere waarschuwing ('niet de vraagtitels aanpassen') stond in
    form.setDescription() -- zichtbaar voor de INVULLERS, die er niets mee kunnen. Hoort in
    een code-comment (voor de beheerder die het script leest), niet in de form-tekst."""
    ronde, project = _ronde_met_project()
    script = genereer_apps_script(ronde, project)
    assert "setDescription" not in script
    assert "volgorde" in script.lower()  # staat nog wel als code-comment voor de beheerder
