"""Importeert een Google Forms-antwoordenexport (.xlsx). Zie docs/DESIGN.md §4.5.

Twee koppelstrategieën, in volgorde:
1. Kolomkop bevat '#<index>' -> koppel via Ronde.vragen[index].les_id. Dit is de normale
   weg voor een via forms_script.py aangemaakt formulier, en werkt ongeacht of het label
   zelf is aangepast of de vraag is herschikt.
2. Geen '#n' gevonden (handgemaakt formulier) -> parse het label als Nederlandse
   dag+maand(+tijd) en koppel op (datum, begin_tijd). Bij twijfel (0 of >1 kandidaten)
   wordt de kolom als 'niet gekoppeld' gerapporteerd -- nooit geraden.

Een lege cel betekent ONBEKEND, nooit 'nee' -- dat onderscheid is echt (niet gereageerd is
iets anders dan niet kunnen)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..domain.formatting import parse_nl_maand, parse_nl_tijd
from ..domain.names import is_exact, stel_voor
from ..model.availability import Antwoordwaarde, Ronde
from ..model.project import Project
from .types import GekoppeldAntwoord, ImportResultaat, NaamProbleem

_WAARDE_MAP: dict[str, Antwoordwaarde] = {"ja": "ja", "misschien": "misschien", "nee": "nee"}
_HEKJE_PATROON = re.compile(r"#(\d+)\s*$")
_LABEL_PATROON = re.compile(
    r"(?P<dag>\d{1,2})\s+(?P<maand>[a-zA-Zé]+)(?:[^\d]*(?P<tijd>\d{1,2}:\d{2}))?"
)


def lees_forms_export(pad: str | Path, ronde: Ronde, project: Project) -> ImportResultaat:
    df = pd.read_excel(pad)
    if df.empty:
        return ImportResultaat(ronde_id=ronde.id, waarschuwingen=["Het bestand bevat geen rijen."])

    kolommen = [str(k) for k in df.columns]
    naamkolom = _vind_kolom(kolommen, ("wie ben je?", "naam"))
    tijdstempelkolom = _vind_kolom(kolommen, ("tijdstempel", "timestamp"))

    vraag_per_index = {v.index: v for v in ronde.vragen}
    kolom_naar_les_id: dict[str, str] = {}
    niet_gekoppeld: list[str] = []

    for kolom in kolommen:
        if kolom in (naamkolom, tijdstempelkolom):
            continue
        hekje = _HEKJE_PATROON.search(kolom)
        if hekje is not None:
            vraag = vraag_per_index.get(int(hekje.group(1)))
            if vraag is not None:
                kolom_naar_les_id[kolom] = vraag.les_id
                continue
        les_id = _koppel_op_label(kolom, project)
        if les_id is not None:
            kolom_naar_les_id[kolom] = les_id
        else:
            niet_gekoppeld.append(kolom)

    lesgevers = project.lesgevers
    naam_naar_lesgever = {lg.naam: lg for lg in lesgevers}

    antwoorden_per_lesgever: dict[str, GekoppeldAntwoord] = {}
    naamproblemen: list[NaamProbleem] = []
    dubbele_reacties: dict[str, int] = {}

    for _, rij in df.iterrows():
        ruwe_naam = "" if naamkolom is None else str(rij.get(naamkolom, "")).strip()
        if not ruwe_naam or ruwe_naam.lower() == "nan":
            continue

        ingevuld_op = None
        if tijdstempelkolom is not None:
            waarde = rij.get(tijdstempelkolom)
            if isinstance(waarde, datetime):
                ingevuld_op = waarde

        waarden: dict[str, Antwoordwaarde] = {}
        for kolom, les_id in kolom_naar_les_id.items():
            cel = rij.get(kolom)
            if pd.isna(cel):
                continue
            tekst = str(cel).strip().lower()
            if not tekst:
                continue
            if tekst in _WAARDE_MAP:
                waarden[les_id] = _WAARDE_MAP[tekst]

        lesgever = naam_naar_lesgever.get(ruwe_naam)
        if lesgever is None:
            voorstellen = stel_voor(ruwe_naam, lesgevers)
            if voorstellen and is_exact(voorstellen[0][1]):
                lesgever = voorstellen[0][0]
            else:
                naamproblemen.append(
                    NaamProbleem(
                        ruwe_naam=ruwe_naam,
                        voorstellen=[(lg.id, score) for lg, score in voorstellen[:5]],
                        waarden=waarden,
                        ingevuld_op=ingevuld_op,
                    )
                )
                continue

        bestaand = antwoorden_per_lesgever.get(lesgever.id)
        if bestaand is None:
            antwoorden_per_lesgever[lesgever.id] = GekoppeldAntwoord(
                lesgever_id=lesgever.id, waarden=waarden, ingevuld_op=ingevuld_op
            )
        else:
            dubbele_reacties[lesgever.naam] = dubbele_reacties.get(lesgever.naam, 1) + 1
            if ingevuld_op is not None and (
                bestaand.ingevuld_op is None or ingevuld_op > bestaand.ingevuld_op
            ):
                antwoorden_per_lesgever[lesgever.id] = GekoppeldAntwoord(
                    lesgever_id=lesgever.id, waarden=waarden, ingevuld_op=ingevuld_op
                )

    waarschuwingen = [
        f"{naam} heeft {aantal}x gereageerd -- de nieuwste reactie is gebruikt."
        for naam, aantal in dubbele_reacties.items()
    ]
    if niet_gekoppeld:
        waarschuwingen.append(
            f"{len(niet_gekoppeld)} kolom(men) konden niet aan een les gekoppeld worden "
            f"en zijn overgeslagen."
        )

    return ImportResultaat(
        ronde_id=ronde.id,
        gekoppelde_antwoorden=list(antwoorden_per_lesgever.values()),
        niet_gekoppelde_kolommen=niet_gekoppeld,
        naamproblemen=naamproblemen,
        waarschuwingen=waarschuwingen,
    )


def _vind_kolom(kolommen: list[str], mogelijke_namen: tuple[str, ...]) -> str | None:
    for kolom in kolommen:
        if kolom.strip().lower() in mogelijke_namen:
            return kolom
    return None


def _koppel_op_label(label: str, project: Project) -> str | None:
    """Terugval voor handgemaakte formulieren zonder '#index'. Koppelt op (dag, maand,
    evt. tijd) -- NOOIT op een jaartal uit de export (dat brak bij seizoenen die over de
    jaarwisseling lopen, zoals sep-apr). Bij 0 of >1 kandidaten: niet koppelen, laat de
    gebruiker het handmatig oplossen."""
    match = _LABEL_PATROON.search(label)
    if match is None:
        return None
    try:
        dag = int(match.group("dag"))
        maand = parse_nl_maand(match.group("maand"))
    except (ValueError, KeyError):
        return None

    tijd_tekst = match.group("tijd")
    tijd = None
    if tijd_tekst:
        try:
            tijd = parse_nl_tijd(tijd_tekst)
        except ValueError:
            tijd = None

    kandidaten = [
        les
        for les in project.lessen
        if les.datum.day == dag
        and les.datum.month == maand
        and (tijd is None or les.begin_tijd == tijd)
    ]
    if len(kandidaten) == 1:
        return kandidaten[0].id
    return None
