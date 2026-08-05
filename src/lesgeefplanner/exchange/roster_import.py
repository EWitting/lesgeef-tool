"""Importeert de lesgeverslijst uit Excel. Vervangt de harde `ValueError` die de oude
`src/importer.py:import_lesgevers()` gaf bij een ontbrekende kolom door een
kolommapping-wizard: als een vereiste kolom niet automatisch herkend wordt, geeft dit de
beschikbare kolommen terug zodat de UI de gebruiker kan laten kiezen, in plaats van de
import gewoon te laten crashen (zie docs/PLAN.md fase 7)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from ..model.entities import Lesgever

DoelVeld = Literal["naam", "ervaren", "actief"]

_TREFWOORDEN: dict[DoelVeld, tuple[str, ...]] = {
    "naam": ("naam", "name"),
    "ervaren": ("ervar", "experience"),
    "actief": ("actief", "active"),
}


@dataclass
class RosterImportResultaat:
    lesgevers: list[Lesgever] = field(default_factory=list)
    waarschuwingen: list[str] = field(default_factory=list)
    # Leeg als alle vereiste kolommen automatisch gevonden zijn. Anders: doelveld -> alle
    # beschikbare kolomnamen in het bestand, voor een keuzelijst per ontbrekend veld.
    kolommapping_nodig: dict[DoelVeld, list[str]] = field(default_factory=dict)


def lees_lesgevers(
    pad: str | Path,
    sheet_naam: str | None = None,
    kolommapping: dict[DoelVeld, str] | None = None,
) -> RosterImportResultaat:
    """Zonder `kolommapping`: probeert kolommen automatisch te herkennen op trefwoorden in
    de header. Lukt dat niet voor een of meer velden, dan komt `kolommapping_nodig` terug
    (leeg == alles gelukt) en is `lesgevers` leeg -- de aanroeper roept dan opnieuw aan met
    een expliciete `kolommapping` op basis van de keuze van de gebruiker."""
    xls = pd.ExcelFile(pad)
    gekozen_sheet = sheet_naam or (
        "Lesgevers" if "Lesgevers" in xls.sheet_names else xls.sheet_names[0]
    )
    df = pd.read_excel(xls, sheet_name=gekozen_sheet)
    kolommen = [str(k) for k in df.columns]

    mapping: dict[DoelVeld, str] = dict(kolommapping or {})
    ontbrekend: dict[DoelVeld, list[str]] = {}
    for doel, trefwoorden in _TREFWOORDEN.items():
        if doel in mapping:
            continue
        gevonden = _vind_kolom(kolommen, trefwoorden)
        if gevonden is not None:
            mapping[doel] = gevonden
        else:
            ontbrekend[doel] = kolommen

    if ontbrekend:
        return RosterImportResultaat(kolommapping_nodig=ontbrekend)

    lesgevers: list[Lesgever] = []
    waarschuwingen: list[str] = []
    for _, row in df.iterrows():
        naam = str(row[mapping["naam"]]).strip()
        if not naam or naam.lower() == "nan":
            continue
        ervaren = _parse_ervaren(row[mapping["ervaren"]], naam, waarschuwingen)
        actief = _parse_actief(row[mapping["actief"]], naam, waarschuwingen)
        lesgevers.append(Lesgever(naam=naam, ervaren=ervaren, actief=actief))

    return RosterImportResultaat(lesgevers=lesgevers, waarschuwingen=waarschuwingen)


def _vind_kolom(kolommen: list[str], trefwoorden: tuple[str, ...]) -> str | None:
    for kolom in kolommen:
        laag = kolom.strip().lower()
        if any(trefwoord in laag for trefwoord in trefwoorden):
            return kolom
    return None


_WAAR = ("true", "ja", "1", "waar", "x", "✓")
_ONWAAR = ("false", "nee", "0", "onwaar")


def _parse_ervaren(waarde, naam: str, waarschuwingen: list[str]) -> bool:
    """Een lege cel betekent hier stilzwijgend 'nee' (net als een leeg vinkje) -- dat is
    geen leesfout om over te waarschuwen, in tegenstelling tot 'actief' hieronder waar een
    lege cel wel een waarschuwing + de veilige aanname (actief) krijgt.

    Herkent ook nog een kaal getal (bv. uit een oud bestand van vóór de ervaren-vlag, met
    een kolom "Ervaring (jaren)") als >=1 jaar, zodat zulke bestanden niet stilzwijgend hun
    ervaring-informatie verliezen bij import."""
    if pd.isna(waarde) or str(waarde).strip() == "":
        return False
    tekst = str(waarde).strip().lower()
    if tekst in _WAAR:
        return True
    if tekst in _ONWAAR:
        return False
    try:
        return float(tekst) >= 1
    except ValueError:
        pass
    waarschuwingen.append(f"{naam}: 'ervaren' niet leesbaar ('{waarde}'), nee aangenomen.")
    return False


def _parse_actief(waarde, naam: str, waarschuwingen: list[str]) -> bool:
    tekst = str(waarde).strip().lower()
    if tekst in _WAAR:
        return True
    if tekst in _ONWAAR:
        return False
    waarschuwingen.append(f"{naam}: 'actief' niet leesbaar ('{waarde}'), actief aangenomen.")
    return True
