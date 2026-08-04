"""Bewerkingen op seizoenen en het weekrooster. Genereert NOOIT automatisch de kalender --
dat gebeurt alleen via een expliciete 'Kalender bijwerken'-actie met bevestiging
(docs/DESIGN.md §4.1, docs/PLAN.md fase 8)."""
from __future__ import annotations

from datetime import date, time

from ..model.entities import Seizoen, WeekSlot
from ..model.project import Project
from .state import state


def voeg_seizoen_toe(naam: str, begin: date, eind: date) -> str:
    assert state.doc is not None
    seizoen = Seizoen(naam=naam, begin=begin, eind=eind)
    with state.doc.muteer(f"Seizoen '{naam}' toegevoegd"):
        state.doc.project.seizoenen.append(seizoen)
    return seizoen.id


def wijzig_seizoen(
    seizoen_id: str,
    naam: str | None = None,
    begin: date | None = None,
    eind: date | None = None,
) -> None:
    assert state.doc is not None
    with state.doc.muteer("Seizoen aangepast"):
        seizoen = _vind_seizoen(state.doc.project, seizoen_id)
        if seizoen is None:
            return
        if naam is not None and naam.strip():
            seizoen.naam = naam.strip()
        if begin is not None:
            seizoen.begin = begin
        if eind is not None:
            seizoen.eind = eind


def verwijder_seizoen(seizoen_id: str) -> None:
    assert state.doc is not None
    with state.doc.muteer("Seizoen verwijderd"):
        state.doc.project.seizoenen = [
            s for s in state.doc.project.seizoenen if s.id != seizoen_id
        ]


def zet_eigen_weekrooster(seizoen_id: str, actief: bool) -> None:
    """actief=True: het seizoen krijgt een KOPIE van het jaarrooster als startpunt (niet
    een lege lijst -- dat zou 'bewust geen lessen' betekenen, zie model/entities.py).
    actief=False: het seizoen volgt weer het jaarrooster (weekrooster=None)."""
    assert state.doc is not None
    with state.doc.muteer("Eigen weekrooster gewijzigd"):
        project = state.doc.project
        seizoen = _vind_seizoen(project, seizoen_id)
        if seizoen is None:
            return
        seizoen.weekrooster = (
            [slot.model_copy() for slot in project.weekrooster] if actief else None
        )


def voeg_weekslot_toe(seizoen_id: str | None, dag: int, begin_tijd: time, eind_tijd: time) -> None:
    """seizoen_id=None -> het jaarrooster; anders het EIGEN weekrooster van dat seizoen
    (moet al aanstaan, zie zet_eigen_weekrooster)."""
    assert state.doc is not None
    with state.doc.muteer("Weekslot toegevoegd"):
        lijst = _vind_weekrooster_lijst(state.doc.project, seizoen_id)
        if lijst is not None:
            lijst.append(WeekSlot(dag=dag, begin_tijd=begin_tijd, eind_tijd=eind_tijd))


def verwijder_weekslot(seizoen_id: str | None, index: int) -> None:
    assert state.doc is not None
    with state.doc.muteer("Weekslot verwijderd"):
        lijst = _vind_weekrooster_lijst(state.doc.project, seizoen_id)
        if lijst is not None and 0 <= index < len(lijst):
            del lijst[index]


def _vind_seizoen(project: Project, seizoen_id: str) -> Seizoen | None:
    return next((s for s in project.seizoenen if s.id == seizoen_id), None)


def _vind_weekrooster_lijst(project: Project, seizoen_id: str | None) -> list[WeekSlot] | None:
    if seizoen_id is None:
        return project.weekrooster
    seizoen = _vind_seizoen(project, seizoen_id)
    if seizoen is None or seizoen.weekrooster is None:
        return None
    return seizoen.weekrooster
