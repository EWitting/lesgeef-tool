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


def test_koppeling_op_volgorde(tmp_path: Path):
    """Kolommen na naam/tijdstempel: eerst de screeningvraag, dan de lesvragen in
    bestandsvolgorde -- gekoppeld aan ronde.vragen op positie, niet op tekst."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)
    anne_id = project.lesgevers[0].id

    # De xlsx-export van een keuzerooster geeft elke rij zijn eigen kolom.
    kolommen = ["Tijdstempel", "Wie ben je?", "Wil je dit seizoen lesgeven?", "Rooster [rij 1]", "Rooster [rij 2]"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja natuurlijk!", "Ja", "Misschien"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert len(resultaat.gekoppelde_antwoorden) == 1
    antwoord = resultaat.gekoppelde_antwoorden[0]
    assert antwoord.lesgever_id == anne_id
    assert antwoord.waarden == {les1.id: "ja", les2.id: "misschien"}
    assert antwoord.doet_mee is True
    assert resultaat.niet_gekoppelde_kolommen == []


def test_naamkolom_met_echte_apps_script_titel_wordt_herkend(tmp_path: Path):
    """Regressietest: forms_script.py genereert 'Wat is je naam?' (vrije tekst, geen
    dropdown meer) -- dat moet net zo herkend worden als het oudere 'Wie ben je?'. Eerder
    werd hier alleen op EXACTE match gezocht, dus 'Wat is je naam?' matchte niets, wat
    zowel de naamherkenning brak (iedereen leek niet-gereageerd) als de kolomtelling (de
    lekkende naamkolom telde mee als een extra beschikbaarheidskolom)."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)
    anne_id = project.lesgevers[0].id

    kolommen = ["Tijdstempel", "Wat is je naam?", "Wil je dit seizoen lesgeven?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja natuurlijk!", "Ja", "Nee"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.waarschuwingen == []
    assert len(resultaat.gekoppelde_antwoorden) == 1
    assert resultaat.gekoppelde_antwoorden[0].lesgever_id == anne_id
    assert resultaat.gekoppelde_antwoorden[0].waarden == {les1.id: "ja", les2.id: "nee"}


def test_herschreven_vraagtekst_blijft_koppelen_op_volgorde(tmp_path: Path):
    """Regressietest: de exacte vraagtekst doet er niet toe, alleen de volgorde."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Kun je op 22 april?", "En op 29 april?"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Ja", "Nee"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden[0].waarden == {les1.id: "ja", les2.id: "nee"}


def test_lege_cel_is_onbekend_niet_nee(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    waarden = resultaat.gekoppelde_antwoorden[0].waarden
    assert les1.id not in waarden  # onbekend, niet 'nee'
    assert waarden[les2.id] == "ja"


def test_dubbele_reactie_nieuwste_wint(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Les 1", "Les 2"]
    rijen = [
        [datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Ja", "Ja"],
        [datetime(2026, 1, 3, 10, 0), "Anne", "Ja", "Nee", "Nee"],
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

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Willem Compleet Onbekend", "Ja", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden == []
    assert len(resultaat.naamproblemen) == 1
    assert resultaat.naamproblemen[0].ruwe_naam == "Willem Compleet Onbekend"


def test_exacte_naam_geeft_geen_naamprobleem(tmp_path: Path):
    """Een naam die precies overeenkomt met een lesgever heeft geen wizard nodig."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Bob", "Ja", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.naamproblemen == []
    assert resultaat.gekoppelde_antwoorden[0].lesgever_id == project.lesgevers[1].id


def test_naamprobleem_bevat_de_antwoorden(tmp_path: Path):
    """Zonder dit kan een opgelost naamprobleem niet alsnog tot een antwoord leiden."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Onbekende Naam", "Ja", "Ja", "Nee"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    probleem = resultaat.naamproblemen[0]
    assert probleem.waarden == {les1.id: "ja", les2.id: "nee"}
    assert probleem.ingevuld_op == datetime(2026, 1, 1, 10, 0)


def test_screening_nee_zet_doet_mee_false(tmp_path: Path):
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Wil je dit seizoen lesgeven?", "Les 1", "Les 2"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Nee", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert resultaat.gekoppelde_antwoorden[0].doet_mee is False


def test_te_weinig_kolommen_geeft_waarschuwing(tmp_path: Path):
    """Volgorde-koppeling gaat ervan uit dat het aantal kolommen klopt -- als dat niet zo
    is (bv. een les is later toegevoegd/verwijderd), moet dat gemeld worden i.p.v.
    stilzwijgend verkeerd te koppelen."""
    project, les1, les2 = _project_met_lessen()
    ronde = _ronde_met_vragen(les1, les2)

    kolommen = ["Tijdstempel", "Wie ben je?", "Doe je mee?", "Alleen les 1"]
    rijen = [[datetime(2026, 1, 1, 10, 0), "Anne", "Ja", "Ja"]]
    pad = tmp_path / "export.xlsx"
    _schrijf_xlsx(pad, kolommen, rijen)

    resultaat = lees_forms_export(pad, ronde, project)
    assert any("2 vragen" in w for w in resultaat.waarschuwingen)
