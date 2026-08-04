from pathlib import Path

import pandas as pd

from lesgeefplanner.exchange.roster_import import lees_lesgevers


def _schrijf_xlsx(pad: Path, kolommen: list[str], rijen: list[list], sheet_naam="Lesgevers"):
    df = pd.DataFrame(rijen, columns=kolommen)
    with pd.ExcelWriter(pad) as schrijver:
        df.to_excel(schrijver, sheet_name=sheet_naam, index=False)


def test_automatische_kolomherkenning(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(
        pad, ["Naam", "Ervaring (jaren)", "Actief"],
        [["Anne", 3, "true"], ["Bob", 0, "false"]],
    )
    resultaat = lees_lesgevers(pad)
    assert resultaat.kolommapping_nodig == {}
    assert len(resultaat.lesgevers) == 2
    anne = next(lg for lg in resultaat.lesgevers if lg.naam == "Anne")
    assert anne.ervaring_jaren == 3
    assert anne.actief is True
    bob = next(lg for lg in resultaat.lesgevers if lg.naam == "Bob")
    assert bob.actief is False


def test_ja_nee_ook_herkend(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(pad, ["Naam", "Ervaring", "Actief"], [["Anne", 1, "Ja"], ["Bob", 2, "Nee"]])
    resultaat = lees_lesgevers(pad)
    assert resultaat.lesgevers[0].actief is True
    assert resultaat.lesgevers[1].actief is False


def test_ontbrekende_kolom_geeft_kolommapping_nodig_ipv_crash(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(pad, ["Wie", "Jaren mee", "Status"], [["Anne", 3, "ja"]])
    resultaat = lees_lesgevers(pad)
    assert resultaat.lesgevers == []
    assert set(resultaat.kolommapping_nodig.keys()) == {"naam", "ervaring_jaren", "actief"}
    assert "Wie" in resultaat.kolommapping_nodig["naam"]


def test_expliciete_kolommapping_lost_ontbrekende_herkenning_op(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(pad, ["Wie", "Jaren mee", "Status"], [["Anne", 3, "ja"]])
    resultaat = lees_lesgevers(
        pad,
        kolommapping={
            "naam": "Wie", "ervaring_jaren": "Jaren mee", "actief": "Status",
        },
    )
    assert resultaat.kolommapping_nodig == {}
    assert resultaat.lesgevers[0].naam == "Anne"
    assert resultaat.lesgevers[0].ervaring_jaren == 3


def test_onleesbare_ervaring_geeft_waarschuwing_niet_crash(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(pad, ["Naam", "Ervaring", "Actief"], [["Anne", "veel", "ja"]])
    resultaat = lees_lesgevers(pad)
    assert resultaat.lesgevers[0].ervaring_jaren == 0
    assert any("Anne" in w for w in resultaat.waarschuwingen)


def test_lege_naam_rij_wordt_overgeslagen(tmp_path: Path):
    pad = tmp_path / "lesgevers.xlsx"
    _schrijf_xlsx(pad, ["Naam", "Ervaring", "Actief"], [["Anne", 1, "ja"], ["", 0, "ja"]])
    resultaat = lees_lesgevers(pad)
    assert len(resultaat.lesgevers) == 1
