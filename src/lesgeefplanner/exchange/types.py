"""Gedeelde vormen voor import-resultaten. Zie docs/DESIGN.md §4.5: dezelfde vorm wordt
gebruikt door forms_import.py (nu) en de latere datumprikker-import (fase 11), zodat de UI
er maar één keer mee hoeft om te gaan."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from ..model.availability import Antwoordwaarde


@dataclass
class GekoppeldAntwoord:
    lesgever_id: str
    waarden: dict[str, Antwoordwaarde] = field(default_factory=dict)  # les_id -> waarde
    ingevuld_op: datetime | None = None


@dataclass
class NaamProbleem:
    """Een naam uit een bestand die niet exact overeenkomt met een lesgever in het
    project. `voorstellen` is (lesgever_id, score) gesorteerd hoog->laag; een mens kiest,
    dit beslist nooit zelf (docs/DESIGN.md conventie 5).

    `waarden`/`ingevuld_op` horen bij forms_import.py (het antwoord van deze rij, bewaard
    zodat het na het kiezen van een lesgever alsnog tot een GekoppeldAntwoord gemaakt kan
    worden). `les_id` hoort bij excel_import.py (welke les deze naam op stond, zodat een
    opgeloste naam een Wijziging kan worden). Bewust hergebruikt in plaats van twee bijna
    identieke dataklassen: beide contexten zijn "een fuzzy-matchprobleem dat een mens moet
    oplossen", en de UI-wizard is er ook maar één (zie docs/DESIGN.md §7:
    dialogen/diff_dialoog.py als herbruikbaar patroon voor dit soort bevestigingen)."""
    ruwe_naam: str
    voorstellen: list[tuple[str, float]] = field(default_factory=list)
    waarden: dict[str, Antwoordwaarde] = field(default_factory=dict)
    ingevuld_op: datetime | None = None
    les_id: str | None = None


@dataclass
class ImportResultaat:
    ronde_id: str
    gekoppelde_antwoorden: list[GekoppeldAntwoord] = field(default_factory=list)
    niet_gekoppelde_kolommen: list[str] = field(default_factory=list)
    naamproblemen: list[NaamProbleem] = field(default_factory=list)
    waarschuwingen: list[str] = field(default_factory=list)


@dataclass
class Wijziging:
    """Eén verschil tussen het project en een teruggelezen Excel-bestand. Zie
    docs/DESIGN.md §4.4."""
    les_id: str
    soort: Literal["toegevoegd", "verwijderd", "status", "titel"]
    lesgever_id: str | None
    oud: str
    nieuw: str
    zekerheid: Literal["exact", "voorstel"] = "exact"
