"""Naam-matching en -weergave. Zie docs/DESIGN.md §4.4 en conventie 5: fuzzy matching levert
een gerangschikte SUGGESTIE op, en beslist nooit zelf. Dit is de vervanging van de oude
`src/importer.py:distance()`, die Levenshtein < 3 stilzwijgend accepteerde (waardoor "Jan"
en "Jen" zomaar aan elkaar gekoppeld werden)."""
from __future__ import annotations

from Levenshtein import distance as levenshtein_distance

from ..model.entities import Lesgever

DREMPEL_EXACT = 0.99


def _score(a: str, b: str) -> float:
    a, b = a.strip().lower(), b.strip().lower()
    if not a and not b:
        return 1.0
    afstand = levenshtein_distance(a, b)
    lengte = max(len(a), len(b), 1)
    return max(0.0, 1.0 - afstand / lengte)


def _beste_score(naam: str, lesgever: Lesgever) -> float:
    """Vergelijkt de volledige naam, de voornaam van de lesgever, en de voornaam van de
    ingevoerde naam tegen de volledige lesgeversnaam -- vangt zowel 'iemand typte alleen
    de voornaam' als 'iemand typte de voornaam omgekeerd getest' af."""
    volledig = _score(naam, lesgever.naam)
    lesgever_delen = lesgever.naam.split()
    lesgever_voornaam = lesgever_delen[0] if lesgever_delen else lesgever.naam
    tegen_voornaam = _score(naam, lesgever_voornaam)
    naam_delen = naam.split()
    ingevoerde_voornaam = naam_delen[0] if naam_delen else naam
    voornaam_tegen_volledig = _score(ingevoerde_voornaam, lesgever.naam)
    return max(volledig, tegen_voornaam, voornaam_tegen_volledig)


def stel_voor(naam: str, lesgevers: list[Lesgever]) -> list[tuple[Lesgever, float]]:
    """Gerangschikte suggesties (hoogste score eerst). Beslist NOOIT zelf -- gebruik
    `is_exact()` om te bepalen of de beste suggestie zonder mens bevestigd mag worden."""
    resultaat = [(lg, _beste_score(naam, lg)) for lg in lesgevers]
    resultaat.sort(key=lambda item: -item[1])
    return resultaat


def is_exact(score: float) -> bool:
    return score >= DREMPEL_EXACT


def display_names(lesgevers: list[Lesgever]) -> dict[str, str]:
    """lesgever.id -> weergavenaam: voornaam als die uniek is binnen de lijst, anders de
    volledige naam. Muteert niets (in tegenstelling tot de oude `import_lesgevers()`, die
    `lesgever.naam` zelf overschreef als de voornaam uniek was)."""
    voornaam_telling: dict[str, int] = {}
    for lg in lesgevers:
        delen = lg.naam.split()
        voornaam = delen[0] if delen else lg.naam
        voornaam_telling[voornaam] = voornaam_telling.get(voornaam, 0) + 1

    resultaat: dict[str, str] = {}
    for lg in lesgevers:
        delen = lg.naam.split()
        voornaam = delen[0] if delen else lg.naam
        resultaat[lg.id] = voornaam if voornaam_telling[voornaam] == 1 else lg.naam
    return resultaat
