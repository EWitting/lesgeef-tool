"""Importeert een Google Forms-antwoordenexport (.xlsx). Zie docs/DESIGN.md §4.5.

De naam- en tijdstempelkolom worden op trefwoord herkend (bevat "naam" resp.
"tijdstempel"/"timestamp" -- geen exacte match, want de vraagtekst zelf kan verschillen:
"Wat is je naam?" bij een Apps Script-formulier, "Wie ben je?" bij een oud-stijl
handgemaakt formulier). Alle ANDERE kolommen koppelen op VOLGORDE, niet op tekst (voor de
bewuste keuze, zie forms_script.py): in bestandsvolgorde 1-op-1 aan de screeningvraag en
dan `ronde.vragen` (gesorteerd op index). Dit gaat ervan uit dat de vraagvolgorde in het
formulier nog overeenkomt met de ronde -- bij twijfel (aantal kolommen klopt niet) wordt
dat als waarschuwing gemeld i.p.v. stilzwijgend verkeerd te koppelen.

Een lege cel betekent ONBEKEND, nooit 'nee' -- dat onderscheid is echt (niet gereageerd is
iets anders dan niet kunnen)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ..domain.names import is_exact, stel_voor
from ..model.availability import Antwoordwaarde, Ronde
from ..model.project import Project
from .types import GekoppeldAntwoord, ImportResultaat, NaamProbleem

_WAARDE_MAP: dict[str, Antwoordwaarde] = {"ja": "ja", "misschien": "misschien", "nee": "nee"}


def lees_forms_export(pad: str | Path, ronde: Ronde, project: Project) -> ImportResultaat:
    df = pd.read_excel(pad)
    if df.empty:
        return ImportResultaat(ronde_id=ronde.id, waarschuwingen=["Het bestand bevat geen rijen."])

    kolommen = [str(k) for k in df.columns]
    # Bevat-checks (niet exacte match): de naamvraag heet "Wat is je naam?" (forms_script.py)
    # of, in een ouder-stijl formulier, "Wie ben je?" -- allebei bevatten "naam" resp. "wie
    # ben je", dus een losse trefwoordenlijst hoeft niet exact de volledige vraagtekst te zijn.
    naamkolom = _vind_kolom(kolommen, ("naam", "wie ben je"))
    tijdstempelkolom = _vind_kolom(kolommen, ("tijdstempel", "timestamp"))

    # Alles behalve naam/tijdstempel, in bestandsvolgorde: eerst de screeningvraag, dan de
    # rooster-rijen (of, bij een oud-stijl formulier met een losse vraag per les, de
    # vragen zelf) -- precies de volgorde waarin forms_script.py ze aanmaakt.
    overige = [k for k in kolommen if k not in (naamkolom, tijdstempelkolom)]
    screeningkolom = overige[0] if overige else None
    vraagkolommen = overige[1:]

    vragen_gesorteerd = sorted(ronde.vragen, key=lambda v: v.index)
    kolom_naar_les_id = {
        kolom: vraag.les_id for kolom, vraag in zip(vraagkolommen, vragen_gesorteerd)
    }
    niet_gekoppeld = vraagkolommen[len(vragen_gesorteerd):]

    waarschuwingen: list[str] = []
    if len(vraagkolommen) != len(vragen_gesorteerd):
        waarschuwingen.append(
            f"Het bestand heeft {len(vraagkolommen)} beschikbaarheidskolom(men), maar de "
            f"ronde heeft {len(vragen_gesorteerd)} vragen -- controleer of de volgorde "
            f"van de vragen nog bij de ronde past. Overtollige kolommen zijn overgeslagen."
        )

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

        doet_mee = _lees_doet_mee(rij, screeningkolom)

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
                        doet_mee=doet_mee,
                    )
                )
                continue

        bestaand = antwoorden_per_lesgever.get(lesgever.id)
        if bestaand is None:
            antwoorden_per_lesgever[lesgever.id] = GekoppeldAntwoord(
                lesgever_id=lesgever.id, waarden=waarden, ingevuld_op=ingevuld_op,
                doet_mee=doet_mee,
            )
        else:
            dubbele_reacties[lesgever.naam] = dubbele_reacties.get(lesgever.naam, 1) + 1
            if ingevuld_op is not None and (
                bestaand.ingevuld_op is None or ingevuld_op > bestaand.ingevuld_op
            ):
                antwoorden_per_lesgever[lesgever.id] = GekoppeldAntwoord(
                    lesgever_id=lesgever.id, waarden=waarden, ingevuld_op=ingevuld_op,
                    doet_mee=doet_mee,
                )

    waarschuwingen += [
        f"{naam} heeft {aantal}x gereageerd -- de nieuwste reactie is gebruikt."
        for naam, aantal in dubbele_reacties.items()
    ]
    if niet_gekoppeld:
        waarschuwingen.append(
            f"{len(niet_gekoppeld)} overtollige kolom(men) konden niet aan een les "
            f"gekoppeld worden en zijn overgeslagen."
        )

    return ImportResultaat(
        ronde_id=ronde.id,
        gekoppelde_antwoorden=list(antwoorden_per_lesgever.values()),
        niet_gekoppelde_kolommen=niet_gekoppeld,
        naamproblemen=naamproblemen,
        waarschuwingen=waarschuwingen,
    )


def _lees_doet_mee(rij, screeningkolom: str | None) -> bool:
    """Geen screeningkolom (handgemaakt formulier zonder die vraag) of een leeg/onbekend
    antwoord -> aannemen dat iemand meedoet (veilige standaard, Antwoord.doet_mee is ook
    standaard True). Alleen een expliciete 'nee' telt als niet-meedoen."""
    if screeningkolom is None:
        return True
    cel = rij.get(screeningkolom)
    if pd.isna(cel):
        return True
    return str(cel).strip().lower() != "nee"


def _vind_kolom(kolommen: list[str], trefwoorden: tuple[str, ...]) -> str | None:
    for kolom in kolommen:
        laag = kolom.strip().lower()
        if any(trefwoord in laag for trefwoord in trefwoorden):
            return kolom
    return None
