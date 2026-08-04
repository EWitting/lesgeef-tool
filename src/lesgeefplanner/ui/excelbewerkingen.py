"""Past een lijst Wijziging (uit exchange/excel_import.py) toe op het project. Net als
lesbewerkingen.py/rondebewerkingen.py: UI-onafhankelijk en testbaar. Toegepaste wijzigingen
krijgen bron='import', vast=True (docs/DESIGN.md §4.4: iemand heeft dit bewust met de hand
in de Drive-sheet gezet)."""
from __future__ import annotations

from ..exchange.types import Wijziging
from ..model.entities import Toewijzing
from .state import state


def pas_wijzigingen_toe(wijzigingen: list[Wijziging]) -> int:
    """Past de gegeven wijzigingen toe (de aanroeper filtert vooraf op wat de gebruiker
    heeft aangevinkt). Geeft het aantal toegepaste wijzigingen terug."""
    assert state.doc is not None
    if not wijzigingen:
        return 0

    with state.doc.muteer("Wijzigingen uit Excel toegepast"):
        project = state.doc.project
        les_by_id = {les.id: les for les in project.lessen}
        toegepast = 0
        for w in wijzigingen:
            les = les_by_id.get(w.les_id)
            if les is None:
                continue

            if w.soort == "toegevoegd" and w.lesgever_id:
                if not any(tw.lesgever_id == w.lesgever_id for tw in les.toewijzingen):
                    les.toewijzingen.append(
                        Toewijzing(lesgever_id=w.lesgever_id, vast=True, bron="import")
                    )
            elif w.soort == "verwijderd" and w.lesgever_id:
                les.toewijzingen = [
                    tw for tw in les.toewijzingen if tw.lesgever_id != w.lesgever_id
                ]
            elif w.soort == "status":
                if w.nieuw.startswith("Vervalt"):
                    reden = w.nieuw[len("Vervalt") :].lstrip(" —-:").strip() or None
                    les.status = "vervallen"
                    les.vervallen_reden = reden
                    les.toewijzingen = []
                else:
                    les.status = "gaat_door"
                    les.vervallen_reden = None
            elif w.soort == "titel":
                les.titel = w.nieuw or None

            les.beschermd = True
            toegepast += 1

    return toegepast
