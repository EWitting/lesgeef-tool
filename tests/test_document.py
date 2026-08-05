import json
import time as time_module
from pathlib import Path

import pytest

from lesgeefplanner.model import Lesgever
from lesgeefplanner.model.project import SCHEMA_VERSION
from lesgeefplanner.store.document import Document
from lesgeefplanner.store.migrations import OnbekendSchemaError, migreer


def test_nieuw_muteer_opslaan_openen(tmp_path: Path):
    doc = Document.nieuw("Testjaar")
    with doc.muteer("Lesgever toegevoegd"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))

    pad = tmp_path / "test.lesplan"
    doc.opslaan(pad)
    assert pad.exists()

    heropend = Document.open(pad)
    assert heropend.project.naam == "Testjaar"
    assert heropend.project.lesgevers[0].naam == "Anne"


def test_undo_herstelt_exact(tmp_path: Path):
    doc = Document.nieuw("Testjaar")
    with doc.muteer("Lesgever toegevoegd"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))
    assert len(doc.project.lesgevers) == 1

    beschrijving = doc.ongedaan_maken()
    assert beschrijving == "Lesgever toegevoegd"
    assert len(doc.project.lesgevers) == 0

    opnieuw_beschrijving = doc.opnieuw()
    assert opnieuw_beschrijving == "Lesgever toegevoegd"
    assert len(doc.project.lesgevers) == 1


def test_undo_stack_max_50():
    doc = Document.nieuw("Testjaar")
    for i in range(51):
        with doc.muteer(f"mutatie {i}"):
            doc.project.lesgevers.append(Lesgever(naam=f"Persoon{i}"))
    assert len(doc._undo_stack) == 50
    assert len(doc.project.lesgevers) == 51


def test_undo_redo_beschrijving_peek():
    doc = Document.nieuw("Testjaar")
    assert doc.volgende_undo_beschrijving() is None
    with doc.muteer("Lesgever toegevoegd"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))
    assert doc.volgende_undo_beschrijving() == "Lesgever toegevoegd"
    assert doc.volgende_redo_beschrijving() is None
    doc.ongedaan_maken()
    assert doc.volgende_undo_beschrijving() is None
    assert doc.volgende_redo_beschrijving() == "Lesgever toegevoegd"


def test_redo_stack_geleegd_na_nieuwe_mutatie():
    doc = Document.nieuw("Testjaar")
    with doc.muteer("eerste"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))
    doc.ongedaan_maken()
    assert doc.kan_opnieuw()

    with doc.muteer("tweede"):
        doc.project.lesgevers.append(Lesgever(naam="Bob"))
    assert not doc.kan_opnieuw()


def test_gewijzigd_vlag(tmp_path: Path):
    doc = Document.nieuw("Testjaar")
    assert not doc.gewijzigd
    with doc.muteer("iets"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))
    assert doc.gewijzigd
    doc.opslaan(tmp_path / "x.lesplan")
    assert not doc.gewijzigd


def test_autosave_debounce(tmp_path: Path):
    doc = Document.nieuw("Testjaar")
    pad = tmp_path / "x.lesplan"
    doc.opslaan(pad)
    with doc.muteer("iets"):
        doc.project.lesgevers.append(Lesgever(naam="Anne"))
    assert doc.autosave_indien_nodig(interval_seconden=999) is False
    assert doc.autosave_indien_nodig(interval_seconden=0) is True
    assert not doc.gewijzigd


def test_backup_gemaakt(tmp_path: Path):
    doc = Document.nieuw("Testjaar")
    pad = tmp_path / "x.lesplan"
    doc.opslaan(pad)
    backups = list((tmp_path / ".lesgeefplanner-backups").glob("x-*.lesplan"))
    assert len(backups) == 1


def test_migratie_te_nieuw_schema_geeft_nette_fout():
    with pytest.raises(OnbekendSchemaError):
        migreer({"schema_version": SCHEMA_VERSION + 1})


def test_migratie_huidige_schema_ongewijzigd():
    data = {"schema_version": SCHEMA_VERSION, "naam": "X"}
    assert migreer(data) == data


def test_migratie_1_naar_2_zet_ervaring_jaren_om_naar_ervaren():
    data = {
        "schema_version": 1, "naam": "X",
        "lesgevers": [
            {"id": "a", "naam": "Anne", "ervaring_jaren": 3, "actief": True},
            {"id": "b", "naam": "Bob", "ervaring_jaren": 0, "actief": True},
        ],
    }
    gemigreerd = migreer(data)
    assert gemigreerd["schema_version"] == SCHEMA_VERSION
    lesgevers = {lg["naam"]: lg for lg in gemigreerd["lesgevers"]}
    assert lesgevers["Anne"]["ervaren"] is True
    assert "ervaring_jaren" not in lesgevers["Anne"]
    assert lesgevers["Bob"]["ervaren"] is False
