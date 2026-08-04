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
