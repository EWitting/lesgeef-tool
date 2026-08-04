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
    ervaring_jaren: int | None = None,
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
        if ervaring_jaren is not None:
            lesgever.ervaring_jaren = ervaring_jaren
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
