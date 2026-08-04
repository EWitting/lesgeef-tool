from pathlib import Path

from lesgeefplanner.ui import foutafhandeling as fa


def test_schrijf_log_maakt_bestand_aan_en_schrijft_details(tmp_path: Path, monkeypatch):
    logpad = tmp_path / "log.txt"
    monkeypatch.setattr(fa, "logbestand_pad", lambda: logpad)

    fa._schrijf_log("ValueError: iets ging mis\n")

    assert logpad.exists()
    inhoud = logpad.read_text(encoding="utf-8")
    assert "ValueError: iets ging mis" in inhoud


def test_schrijf_log_voegt_toe_in_plaats_van_te_overschrijven(tmp_path: Path, monkeypatch):
    logpad = tmp_path / "log.txt"
    monkeypatch.setattr(fa, "logbestand_pad", lambda: logpad)

    fa._schrijf_log("eerste fout")
    fa._schrijf_log("tweede fout")

    inhoud = logpad.read_text(encoding="utf-8")
    assert "eerste fout" in inhoud
    assert "tweede fout" in inhoud


def test_schrijf_log_faalt_niet_bij_onschrijfbaar_pad(tmp_path: Path, monkeypatch):
    onmogelijk_pad = tmp_path / "bestaat" / "niet" / "??invalid::" / "log.txt"
    monkeypatch.setattr(fa, "logbestand_pad", lambda: onmogelijk_pad)
    fa._schrijf_log("mag geen exception geven")  # geen assert nodig -- mag niet crashen
