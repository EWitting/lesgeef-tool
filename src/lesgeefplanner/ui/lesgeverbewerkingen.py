"""Bewerkingen op de lesgeverslijst. Zie docs/DESIGN.md §7 (dialogen/lesgevers.py stond al
in de mappenstructuur maar was aan geen enkele fase toegewezen -- zonder dit kan een
gebruiker helemaal geen lesgevers aanmaken). Net als lesbewerkingen.py/rondebewerkingen.py:
UI-onafhankelijke functies, testbaar zonder browser."""
from __future__ import annotations

from ..model.entities import Lesgever
from .state import state


def voeg_lesgever_toe(naam: str) -> str:
    assert state.doc is not None
    lesgever = Lesgever(naam=naam.strip())
    with state.doc.muteer("Lesgever toegevoegd"):
        state.doc.project.lesgevers.append(lesgever)
    return lesgever.id


def wijzig_lesgever(
    lesgever_id: str,
    naam: str | None = None,
    ervaren: bool | None = None,
    actief: bool | None = None,
) -> None:
    assert state.doc is not None
    with state.doc.muteer("Lesgever aangepast"):
        lesgever = next(
            (l for l in state.doc.project.lesgevers if l.id == lesgever_id), None
        )
        if lesgever is None:
            return
        if naam is not None and naam.strip():
            lesgever.naam = naam.strip()
        if ervaren is not None:
            lesgever.ervaren = ervaren
        if actief is not None:
            lesgever.actief = actief


def verwijder_lesgever(lesgever_id: str) -> None:
    """Verwijdert de lesgever EN eventuele toewijzingen aan die lesgever, zodat er geen
    verweesde verwijzingen achterblijven die als '? (onbekend)' zouden opduiken."""
    assert state.doc is not None
    with state.doc.muteer("Lesgever verwijderd"):
        project = state.doc.project
        project.lesgevers = [l for l in project.lesgevers if l.id != lesgever_id]
        for les in project.lessen:
            if any(tw.lesgever_id == lesgever_id for tw in les.toewijzingen):
                les.toewijzingen = [
                    tw for tw in les.toewijzingen if tw.lesgever_id != lesgever_id
                ]


def samenvoeg_geimporteerde_lesgevers(geimporteerd: list[Lesgever]) -> int:
    """Voegt geïmporteerde lesgevers (exchange/roster_import.py) samen met de bestaande
    lijst: exacte naammatch -> ervaring/actief bijwerken, geen match -> toevoegen als
    nieuwe lesgever. Geeft het aantal verwerkte lesgevers terug."""
    assert state.doc is not None
    if not geimporteerd:
        return 0
    with state.doc.muteer("Lesgevers geïmporteerd uit Excel"):
        project = state.doc.project
        bestaand_by_naam = {lg.naam: lg for lg in project.lesgevers}
        for nieuw in geimporteerd:
            bestaand = bestaand_by_naam.get(nieuw.naam)
            if bestaand is not None:
                bestaand.ervaren = nieuw.ervaren
                bestaand.actief = nieuw.actief
            else:
                project.lesgevers.append(nieuw)
    return len(geimporteerd)
