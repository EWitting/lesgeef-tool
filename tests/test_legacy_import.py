from datetime import date, time
from pathlib import Path

import pandas as pd

from lesgeefplanner.exchange.legacy_import import importeer_oude_opzet

# Zelfde inhoud als de echte data/planning.yml op het moment van de rewrite (docs/PLAN.md
# fase 8 acceptatiecriterium: "importeert met precies de verwachte waarschuwingen over
# Lustrum Trip en Vooka").
_PLANNING_YAML = """
seizoenen:
  - naam: "PKursus"
    begin: "2026-03-16"
    eind: "2026-04-19"
    weekrooster: []
  - naam: "Voorseizoen 1"
    begin: "2026-04-19"
    eind: "2026-05-10"

weekrooster:
  - dag: "woensdag"
    tijd: "16:00 - 19:00"
  - dag: "zaterdag"
    tijd: "14:00 - 17:00"
  - dag: "zondag"
    tijd: "14:00 - 17:00"

extra-lessen:
  - naam: "Cursus: Windroos / Sturen (+overstag)"
    dagen:
      - datum: "2026-03-22"
        tijd: "14:00 - 17:00"
  - naam: "Bussessie (voorbehoud)"
    dagen:
      - datum: "2026-04-12"
        tijd: "10:00 - 17:00"

activiteiten:
  - naam: "Seizoen Start"
    datum: "2026-04-19"
    les-gaat-door: true
  - naam: "Beka"
    datum: "2026-04-25"
    les-gaat-door: false
  - naam: "Beka"
    datum: "2026-04-26"
    les-gaat-door: false
  - naam: "Lustrum Trip"
    datum: "2026-05-16"
    les-gaat-door: false
  - naam: "Lustrum Trip"
    datum: "2026-05-17"
    les-gaat-door: false
  - naam: "Vooka"
    datum: "2026-05-30"
    les-gaat-door: false
  - naam: "Vooka"
    datum: "2026-05-31"
    les-gaat-door: false
"""


def test_import_geeft_precies_de_verwachte_waarschuwingen(tmp_path: Path):
    pad = tmp_path / "planning.yml"
    pad.write_text(_PLANNING_YAML, encoding="utf-8")

    project, waarschuwingen = importeer_oude_opzet(pad)

    assert len(waarschuwingen) == 4
    assert all("Lustrum Trip" in w or "Vooka" in w for w in waarschuwingen)
    assert sum("Lustrum Trip" in w for w in waarschuwingen) == 2
    assert sum("Vooka" in w for w in waarschuwingen) == 2


def test_pkursus_lege_weekrooster_genereert_geen_lessen(tmp_path: Path):
    pad = tmp_path / "planning.yml"
    pad.write_text(_PLANNING_YAML, encoding="utf-8")
    project, _ = importeer_oude_opzet(pad)

    pkursus = next(s for s in project.seizoenen if s.naam == "PKursus")
    lessen_pkursus = [l for l in project.lessen if l.seizoen_id == pkursus.id and l.soort == "regulier"]
    assert lessen_pkursus == []


def test_seizoen_start_en_beka_toegepast(tmp_path: Path):
    pad = tmp_path / "planning.yml"
    pad.write_text(_PLANNING_YAML, encoding="utf-8")
    project, waarschuwingen = importeer_oude_opzet(pad)

    seizoen_start = next(l for l in project.lessen if l.titel == "Seizoen Start")
    assert seizoen_start.datum == date(2026, 4, 19)
    assert seizoen_start.status == "gaat_door"

    beka_lessen = [l for l in project.lessen if l.titel == "Beka"]
    assert len(beka_lessen) == 2
    assert all(l.status == "vervallen" and l.vervallen_reden == "Beka" for l in beka_lessen)


def test_extra_lessen_toegevoegd(tmp_path: Path):
    pad = tmp_path / "planning.yml"
    pad.write_text(_PLANNING_YAML, encoding="utf-8")
    project, _ = importeer_oude_opzet(pad)

    extra = [l for l in project.lessen if l.soort == "extra"]
    assert len(extra) == 2
    namen = {l.titel for l in extra}
    assert "Bussessie (voorbehoud)" in namen


def test_lesgevers_xlsx_wordt_geimporteerd(tmp_path: Path):
    pad = tmp_path / "planning.yml"
    pad.write_text(_PLANNING_YAML, encoding="utf-8")

    lesgevers_pad = tmp_path / "lesgevers.xlsx"
    df = pd.DataFrame(
        [["Anne", 3, "true"], ["Bob", 0, "false"]], columns=["Naam", "Ervaring (jaren)", "Actief"]
    )
    with pd.ExcelWriter(lesgevers_pad) as schrijver:
        df.to_excel(schrijver, sheet_name="Lesgevers", index=False)

    project, waarschuwingen = importeer_oude_opzet(pad, lesgevers_xlsx=lesgevers_pad)
    namen = {lg.naam for lg in project.lesgevers}
    assert namen == {"Anne", "Bob"}
    # Namen blijven volledig -- geen inkorting zoals de oude import_lesgevers() deed.
    anne = next(lg for lg in project.lesgevers if lg.naam == "Anne")
    assert anne.ervaren is True  # 3 jaar -> boven de (bewust simpele) 1-jaar-drempel
