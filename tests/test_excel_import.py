"""Round-trip: exporteer, wijzig het bestand zoals een mens dat zou doen, importeer terug.
Dit is het expliciete acceptatiecriterium uit docs/PLAN.md fase 7."""
from datetime import date, time
from pathlib import Path

import openpyxl

from lesgeefplanner.exchange.excel_export import export_planning
from lesgeefplanner.exchange.excel_import import lees_sheet
from lesgeefplanner.model import Lesgever, Project, Seizoen, Toewijzing
from lesgeefplanner.model.entities import Herkomst, Les


def _project() -> tuple[Project, Les]:
    project = Project(naam="Test")
    seizoen = Seizoen(naam="Voorseizoen 1", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
    project.seizoenen = [seizoen]
    anne = Lesgever(naam="Anne", ervaren=True)
    bob = Lesgever(naam="Bob")
    project.lesgevers = [anne, bob]

    les = Les(
        datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
        seizoen_id=seizoen.id, herkomst=Herkomst(seizoen_id=seizoen.id, weekslot_index=0),
        toewijzingen=[Toewijzing(lesgever_id=anne.id, vast=True)],
    )
    project.lessen = [les]
    return project, les


def test_round_trip_naam_wijziging_geeft_precies_een_wijziging(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    ws = wb["Planning"]
    # Vervang Anne door Bob in de lesgeverkolom (rij 2 = eerste les, kolom F = eerste lesgever)
    ws.cell(row=2, column=6, value="Bob")
    wb.save(pad)

    wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(pad, project)

    assert naamproblemen == []
    assert niet_gekoppeld == []
    assert len(wijzigingen) == 2
    soorten = {(w.soort, w.lesgever_id) for w in wijzigingen}
    assert soorten == {
        ("toegevoegd", project.lesgevers[1].id),
        ("verwijderd", project.lesgevers[0].id),
    }


def test_meta_blad_verwijderen_breekt_koppeling_niet(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    del wb["_meta"]
    ws = wb["Planning"]
    ws.cell(row=2, column=9, value="Nieuwe titel")  # Info-kolom
    wb.save(pad)

    wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(pad, project)
    assert niet_gekoppeld == []
    assert len(wijzigingen) == 1
    assert wijzigingen[0].soort == "titel"
    assert wijzigingen[0].nieuw == "Nieuwe titel"


def test_geen_wijzigingen_als_niets_veranderd(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(pad, project)
    assert wijzigingen == []
    assert naamproblemen == []
    assert niet_gekoppeld == []


def test_geen_les_status_wijziging(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    ws = wb["Planning"]
    for col in (6, 7, 8):
        ws.cell(row=2, column=col, value=None)
    ws.cell(row=2, column=6, value="Geen les — Ziek")
    wb.save(pad)

    wijzigingen, _, niet_gekoppeld = lees_sheet(pad, project)
    assert niet_gekoppeld == []
    status_wijzigingen = [w for w in wijzigingen if w.soort == "status"]
    assert len(status_wijzigingen) == 1
    assert "Ziek" in status_wijzigingen[0].nieuw


def test_onbekende_naam_geeft_naamprobleem_met_les_id(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    ws = wb["Planning"]
    ws.cell(row=2, column=7, value="Compleet Onbekende Naam")
    wb.save(pad)

    wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(pad, project)
    assert len(naamproblemen) == 1
    assert naamproblemen[0].les_id == les.id
    assert naamproblemen[0].ruwe_naam == "Compleet Onbekende Naam"


def test_meta_project_id_mismatch_valt_terug_op_code(tmp_path: Path):
    """Als het _meta-blad bij een ANDER project hoort (bv. per ongeluk het verkeerde
    bestand geopend), moet de Code-kolom het nog steeds redden."""
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    meta = wb["_meta"]
    for row in meta.iter_rows():
        if row[0].value == "project_id":
            row[1].value = "een-ander-project-id"
    ws = wb["Planning"]
    ws.cell(row=2, column=9, value="Andere titel")
    wb.save(pad)

    wijzigingen, _, niet_gekoppeld = lees_sheet(pad, project)
    assert niet_gekoppeld == []
    assert any(w.soort == "titel" and w.nieuw == "Andere titel" for w in wijzigingen)


def test_niet_koppelbare_rij_bij_verwijderde_meta_en_code(tmp_path: Path):
    project, les = _project()
    pad = tmp_path / "planning.xlsx"
    export_planning(project, pad)

    wb = openpyxl.load_workbook(pad)
    del wb["_meta"]
    ws = wb["Planning"]
    ws.cell(row=2, column=1, value="")  # Code wissen
    ws.cell(row=2, column=4, value="onherkenbare datumtekst")  # Datum onbruikbaar maken
    wb.save(pad)

    wijzigingen, naamproblemen, niet_gekoppeld = lees_sheet(pad, project)
    assert len(niet_gekoppeld) == 1
