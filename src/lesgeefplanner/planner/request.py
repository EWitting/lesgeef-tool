"""Wat de solver nodig heeft om te kunnen oplossen. Zie docs/DESIGN.md §4.2."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..domain.beschikbaarheid import verzamel_beschikbaarheid
from ..model.availability import Antwoordwaarde
from ..model.config import SolverConfig
from ..model.entities import Les, Lesgever, les_seizoen_id
from ..model.project import Project
from ..model.scope import Scope


@dataclass
class PlanRequest:
    lessen_in_scope: list[Les]
    # ALLE andere lessen die doorgaan in dezelfde seizoenen, inclusief het verleden --
    # nodig voor het tellen van weekconflicten en werkverdeling (zie docs/DESIGN.md §4.2).
    lessen_context: list[Les]
    lesgevers: list[Lesgever]
    beschikbaarheid: dict[tuple[str, str], Antwoordwaarde]  # (lesgever_id, les_id)
    config: SolverConfig
    peildatum: date


def bouw_request(project: Project, scope: Scope, peildatum: date) -> PlanRequest:
    """Bouwt een PlanRequest uit het project. Dit is de plek waar scope-fouten insluipen:
    lessen_in_scope moet ALLEEN lessen bevatten die de scope daadwerkelijk raakt, en
    lessen_context moet ALLE overige gaat_door-lessen in diezelfde seizoenen bevatten
    (ook uit het verleden), anders klopt de werkverdeling en weekconflict-telling niet."""
    lessen_in_scope = [
        les
        for les in project.lessen
        if les.status == "gaat_door" and scope.bevat(les, peildatum)
    ]
    scope_ids = {les.id for les in lessen_in_scope}
    seizoenen_in_scope = {les_seizoen_id(les) for les in lessen_in_scope}

    lessen_context = [
        les
        for les in project.lessen
        if les.status == "gaat_door"
        and les.id not in scope_ids
        and les_seizoen_id(les) in seizoenen_in_scope
    ]

    lesgevers = [lg for lg in project.lesgevers if lg.actief]
    beschikbaarheid = verzamel_beschikbaarheid(project)

    return PlanRequest(
        lessen_in_scope=lessen_in_scope,
        lessen_context=lessen_context,
        lesgevers=lesgevers,
        beschikbaarheid=beschikbaarheid,
        config=project.solver_config,
        peildatum=peildatum,
    )
