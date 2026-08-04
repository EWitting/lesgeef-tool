from pathlib import Path

from lesgeefplanner.store.instellingen import laad_recente_bestanden, voeg_recent_bestand_toe


def test_leeg_zonder_bestand(tmp_path: Path):
    assert laad_recente_bestanden(tmp_path) == []


def test_toevoegen_en_laden(tmp_path: Path):
    bestand1 = tmp_path / "a.lesplan"
    bestand1.write_text("{}")
    bestand2 = tmp_path / "b.lesplan"
    bestand2.write_text("{}")

    voeg_recent_bestand_toe(bestand1, tmp_path)
    voeg_recent_bestand_toe(bestand2, tmp_path)

    recent = laad_recente_bestanden(tmp_path)
    assert recent[0] == str(bestand2.resolve())
    assert recent[1] == str(bestand1.resolve())


def test_dubbel_toegevoegd_komt_bovenaan_niet_dubbel(tmp_path: Path):
    bestand = tmp_path / "a.lesplan"
    bestand.write_text("{}")
    voeg_recent_bestand_toe(bestand, tmp_path)
    voeg_recent_bestand_toe(bestand, tmp_path)
    recent = laad_recente_bestanden(tmp_path)
    assert recent == [str(bestand.resolve())]


def test_verwijderd_bestand_verdwijnt_uit_lijst(tmp_path: Path):
    bestand = tmp_path / "a.lesplan"
    bestand.write_text("{}")
    voeg_recent_bestand_toe(bestand, tmp_path)
    bestand.unlink()
    assert laad_recente_bestanden(tmp_path) == []


def test_max_aantal_recente_bestanden(tmp_path: Path):
    for i in range(10):
        b = tmp_path / f"{i}.lesplan"
        b.write_text("{}")
        voeg_recent_bestand_toe(b, tmp_path)
    assert len(laad_recente_bestanden(tmp_path)) == 8
