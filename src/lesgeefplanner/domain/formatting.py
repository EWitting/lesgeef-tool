"""Nederlandse datum-/tijdopmaak, zonder afhankelijkheid van de systeemlocale.

De oude code riep `locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')` aan, wat toevallig werkte
op de ontwikkelmachine maar niet gegarandeerd is op een andere Windows-installatie (het
locale-pakket is daar vaak niet geïnstalleerd). Deze module gebruikt in plaats daarvan eigen
opzoektabellen."""
from __future__ import annotations

from datetime import date, time

DAGEN_NL = [
    "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag",
]
DAGEN_NL_KORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]

MAANDEN_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]
MAANDEN_NL_KORT = [
    "jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec",
]

_MAAND_NAAR_NUMMER = {naam: i + 1 for i, naam in enumerate(MAANDEN_NL_KORT)}
_MAAND_NAAR_NUMMER.update({naam: i + 1 for i, naam in enumerate(MAANDEN_NL)})


def format_dag(d: date, kort: bool = True) -> str:
    namen = DAGEN_NL_KORT if kort else DAGEN_NL
    return namen[d.weekday()]


def format_datum(d: date, met_jaar: bool = False) -> str:
    """bv. 'zo 19 apr' of 'zondag 19 april 2026' als met_jaar en niet kort."""
    dag = format_dag(d)
    maand = MAANDEN_NL_KORT[d.month - 1]
    basis = f"{dag} {d.day} {maand}"
    return f"{basis} {d.year}" if met_jaar else basis


def format_datum_lang(d: date) -> str:
    """bv. 'zondag 19 april 2026'."""
    return f"{DAGEN_NL[d.weekday()]} {d.day} {MAANDEN_NL[d.month - 1]} {d.year}"


def format_tijd(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def format_tijdvak(begin: time, eind: time) -> str:
    return f"{format_tijd(begin)} - {format_tijd(eind)}"


def parse_nl_maand(naam: str) -> int:
    """Geeft het maandnummer (1-12) voor een Nederlandse maandnaam, kort of lang, ongeacht
    hoofdlettergebruik. Gooit ValueError als de naam niet herkend wordt."""
    sleutel = naam.strip().lower()
    if sleutel not in _MAAND_NAAR_NUMMER:
        raise ValueError(f"Onbekende Nederlandse maandnaam: {naam!r}")
    return _MAAND_NAAR_NUMMER[sleutel]


def parse_nl_tijd(s: str) -> time:
    """Parseert 'HH:MM' naar een time-object."""
    uur_str, minuut_str = s.strip().split(":")
    return time(int(uur_str), int(minuut_str))
