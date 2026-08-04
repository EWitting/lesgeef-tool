"""Bewerkingen op een enkele les: toewijzen, vastzetten, wissen, vervallen, tijd/titel
aanpassen, extra lessen toevoegen/verwijderen.

Elke functie muteert via `state.doc.muteer(...)` (de enige toegestane weg, zie
store/document.py) en zet, waar de bewerking de les inhoudelijk verandert, `beschermd = True`
zodat een latere kalender-hergeneratie (domain/calendar.py) deze les nooit stilzwijgend
aanraakt. Toewijzingen die hier vandaan komen krijgen altijd `bron='handmatig', vast=True`
(docs/DESIGN.md: een lesgever met de hand neerzetten is een bewuste, vaste keuze)."""
from __future__ import annotations

from datetime import date, time

from ..model.entities import Les, Toewijzing
from ..model.project import Project
from .state import state


def vind_les(project: Project, les_id: str) -> Les | None:
    return next((l for l in project.lessen if l.id == les_id), None)


def aantal_lessen_voor(project: Project, lesgever_id: str) -> int:
    """Aantal keer dat deze lesgever is ingedeeld op een les die doorgaat."""
    return sum(
        1
        for les in project.lessen
        if les.status == "gaat_door"
        for tw in les.toewijzingen
        if tw.lesgever_id == lesgever_id
    )


def wijs_lesgever_toe(les_id: str, slot_index: int, lesgever_id: str) -> bool:
    """Wijst toe op de gegeven slotpositie (vervangt als die al bezet is, voegt anders toe
    aan het eind). Geeft False (zonder iets te wijzigen) als deze lesgever al op deze les
    staat -- dubbel indelen is nooit de bedoeling."""
    assert state.doc is not None
    project = state.doc.project
    les = vind_les(project, les_id)
    if les is None:
        return False
    if any(tw.lesgever_id == lesgever_id for tw in les.toewijzingen):
        return False

    with state.doc.muteer("Lesgever toegewezen"):
        les = vind_les(state.doc.project, les_id)
        assert les is not None
        nieuw = Toewijzing(lesgever_id=lesgever_id, vast=True, bron="handmatig")
        if slot_index < len(les.toewijzingen):
            les.toewijzingen[slot_index] = nieuw
        else:
            les.toewijzingen.append(nieuw)
        les.beschermd = True
    return True


def wis_toewijzing(les_id: str, slot_index: int) -> None:
    assert state.doc is not None
    with state.doc.muteer("Toewijzing gewist"):
        les = vind_les(state.doc.project, les_id)
        if les is None or slot_index >= len(les.toewijzingen):
            return
        del les.toewijzingen[slot_index]
        les.beschermd = True


def wissel_vast(les_id: str, slot_index: int) -> None:
    assert state.doc is not None
    with state.doc.muteer("Vastzetten aangepast"):
        les = vind_les(state.doc.project, les_id)
        if les is None or slot_index >= len(les.toewijzingen):
            return
        les.toewijzingen[slot_index].vast = not les.toewijzingen[slot_index].vast
        les.beschermd = True


def markeer_vervallen(les_id: str, reden: str) -> None:
    assert state.doc is not None
    with state.doc.muteer("Les vervalt"):
        les = vind_les(state.doc.project, les_id)
        if les is None:
            return
        les.status = "vervallen"
        les.vervallen_reden = reden.strip() or None
        les.toewijzingen = []
        les.beschermd = True


def markeer_gaat_weer_door(les_id: str) -> None:
    assert state.doc is not None
    with state.doc.muteer("Les gaat weer door"):
        les = vind_les(state.doc.project, les_id)
        if les is None:
            return
        les.status = "gaat_door"
        les.vervallen_reden = None
        les.beschermd = True


def wijzig_tijd(les_id: str, begin_tijd: time, eind_tijd: time) -> None:
    assert state.doc is not None
    with state.doc.muteer("Tijd aangepast"):
        les = vind_les(state.doc.project, les_id)
        if les is None:
            return
        les.begin_tijd = begin_tijd
        les.eind_tijd = eind_tijd
        les.beschermd = True


def wijzig_titel(les_id: str, titel: str) -> None:
    assert state.doc is not None
    with state.doc.muteer("Titel aangepast"):
        les = vind_les(state.doc.project, les_id)
        if les is None:
            return
        les.titel = titel.strip() or None
        les.beschermd = True


def verwijder_extra_les(les_id: str) -> bool:
    """Alleen extra lessen mogen verwijderd worden -- reguliere, gegenereerde lessen horen
    via de kalender-diff (fase 8) te verdwijnen, niet los."""
    assert state.doc is not None
    project = state.doc.project
    les = vind_les(project, les_id)
    if les is None or les.soort != "extra":
        return False
    with state.doc.muteer("Extra les verwijderd"):
        state.doc.project.lessen = [
            l for l in state.doc.project.lessen if l.id != les_id
        ]
    return True


def voeg_extra_les_toe(datum: date, begin_tijd: time, eind_tijd: time, titel: str) -> str:
    """Geeft het id van de nieuwe les terug."""
    assert state.doc is not None
    nieuwe_les = Les(
        datum=datum,
        begin_tijd=begin_tijd,
        eind_tijd=eind_tijd,
        titel=titel.strip() or None,
        soort="extra",
        beschermd=True,
    )
    with state.doc.muteer("Extra les toegevoegd"):
        state.doc.project.lessen.append(nieuwe_les)
    return nieuwe_les.id
