from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

from lesgeefplanner.exchange.forms_import import lees_forms_export
from lesgeefplanner.model import Lesgever, Project, Ronde, RondeVraag, Scope
from lesgeefplanner.model.entities import Les


def _project_met_lessen() -> tuple[Project, Les, Les]:
    project = Project(naam="T")
    les1 = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    les2 = Les(datum=date(2026, 4, 29), begin_tijd=time(16, 0), eind_tijd=time(19, 0))
    project.lessen = [les1, les2]
    project.lesgevers = [Lesgever(naam="Anne"), Lesgever(naam="Bob")]
    return project, les1, les2


def _ronde_met_vragen(les1: Les, les2: Les) -> Ronde:
    return Ronde(
        naam="R1",
        aangemaakt_op=datetime(2026, 1, 1),
        scope=Scope(),
        vragen=[
            RondeVraag(index=1, les_id=les1.id, label="woensdag 22 april 2026 16:00 - 19:00"),
            RondeVraag(index=2, les_id=les2.id, label="woensdag 29 april 2026 16:00 - 19:00"),
        ],
    )


def _schrijf_xlsx(pad: Path, kolommen: list[str], rijen: list[list]) -> None:
    df = pd.DataFrame(rijen, columns=kolommen)
    df.to_excel(pad, index=False)


def test_koppeling_op_hekje(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)
    anne_id = project.lesgevers[0].id

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Misschien"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert len(resultaat.gekoppelde_antwoorden) == 1
    antwoord = resultaat.gekoppelde_antwoorden[0]
    assert antwoord.lesgever_id == anne_id
    assert antwoord.waarden == {les1.id: "ja", les2.id: "misschien"}
    assert resultaat.niet_gekoppelde_kolommen == []


def test_hernoemd_label_blijft_koppelen_via_hekje(tmp_path: Path):
    """Regressietest: zelfs als iemand het label herschrijft, moet '#index' het nog steeds
    laten werken."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Kun je op 22 april? #1", "En op 29 april? #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Nee"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden[0].waarden == {les1.id: "ja", les2.id: "nee"}


def test_terugval_labelparsing_zonder_hekje(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Naam", "Kun je lesgeven op woensdag 22 april 16:00?"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden[0].waarden == {les1.id: "ja"}


def test_lege_cel_is_onbekend_niet_nee(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    waarden = resultaat.gekoppelde_antwoorden[0].waarden
    assert les1.id not in waarden  # onbekend, niet 'nee'
    assert waarden[les2.id] == "ja"


def test_dubbele_reactie_nieuwste_wint(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [
        [datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Ja"],
        [datetime(2026, 1, 3, 10, 0), "Anne", "Nee", "Nee"],
    ]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert len(resultaat.gekoppelde_antwoorden) == 1
    assert resultaat.gekoppelde_antwoorden[0].waarden == {les1.id: "nee", les2.id: "nee"}
    assert any("2x gereageerd" in w for w in resultaat.waarschuwingen)


def test_onbekende_naam_geeft_naamprobleem(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Willem Compleet Onbekend", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden == []
    assert len(resultaat.naamproblemen) == 1
    assert resultaat.naamproblemen[0].ruwe_naam == "Willem Compleet Onbekend"


def test_dropdown_naam_is_altijd_exact(tmp_path: Path):
    """Met de door forms_script.py gegenereerde dropdown is de naam gegarandeerd exact --
    geen wizard nodig."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Bob", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.naamproblemen == []
    assert resultaat.gekoppelde_antwoorden[0].lesgever_id == project.lesgevers[1].id


def test_naamprobleem_bevat_de_antwoorden(tmp_path: Path):
    """Zonder dit kan een opgelost naamprobleem niet alsnog tot een antwoord leiden."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", f"{ronde.vragen[0].label} #1", f"{ronde.vragen[1].label} #2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Onbekende Naam", "Ja", "Nee"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    probleem = resultaat.naamproblemen[0]
    assert probleem.waarden == {les1.id: "ja", les2.id: "nee"}
    assert probleem.ingevuld_op == datetime(2026, 1, 1, 10, 0)


def test_niet_koppelbare_kolom_wordt_gerapporteerd(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Deze kolom betekent niets herkenbaars"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert "Deze kolom betekent niets herkenbaars" in resultaat.niet_gekoppelde_kolommen
