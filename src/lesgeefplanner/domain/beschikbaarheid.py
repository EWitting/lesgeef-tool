"""Verzamelt beschikbaarheid uit alle rondes van een project. Gedeeld tussen de solver
(planner/request.py) en de analyse (domain/analysis.py) zodat "wat iemand heeft geantwoord"
overal hetzelfde betekent."""
from __future__ import annotations

from ..model.availability import Antwoordwaarde
from ..model.project import Project


def verzamel_beschikbaarheid(project: Project) -> dict[tuple[str, str], Antwoordwaarde]:
    """(lesgever_id, les_id) -> antwoord. Nieuwste ronde wint bij overlap. Een lesgever die
    'nee' antwoordde op de screeningvraag (doet_mee=False) telt als volledig onbeschikbaar
    -- zijn/haar antwoorden in die ronde worden genegeerd."""
    resultaat: dict[tuple[str, str], Antwoordwaarde] = {}
    for ronde in sorted(project.rondes, key=lambda r: r.aangemaakt_op):
        for antwoord in ronde.antwoorden:
            if not antwoord.doet_mee:
                continue
            for les_id, waarde in antwoord.waarden.items():
                resultaat[(antwoord.lesgever_id, les_id)] = waarde
    return resultaat


def niet_meedoende_lesgevers(project: Project, les_ids: set[str]) -> set[str]:
    """lesgever_ids die in de nieuwste ronde die minstens één van `les_ids` raakt expliciet
    'nee' antwoordden op de screeningvraag (doet_mee=False) -- bewust niet beschikbaar voor
    die periode, in tegenstelling tot 'nog niet gereageerd' (dat blijft gewoon 'onbekend',
    zie verzamel_beschikbaarheid hierboven en analysis.py:_analyseer_reacties)."""
    laatste: dict[str, bool] = {}
    for ronde in sorted(project.rondes, key=lambda r: r.aangemaakt_op):
        if not {vraag.les_id for vraag in ronde.vragen} & les_ids:
            continue
        for antwoord in ronde.antwoorden:
            laatste[antwoord.lesgever_id] = antwoord.doet_mee
    return {lesgever_id for lesgever_id, doet_mee in laatste.items() if not doet_mee}
