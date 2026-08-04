"""Verzamelt alle termen van de solver-objectivefunctie zodat de score achteraf uit te
leggen is (docs/DESIGN.md §4.2: "Waarom deze score?"). Zonder dit is de objective-functie
een black box en is de config-tuning gokwerk."""
from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIE_LABELS = {
    "tekort": "Te weinig lesgevers",
    "bezetting_bonus": "Extra lesgever (bonus)",
    "misschien": "Misschien-antwoord ingedeeld",
    "geen_ervaren": "Geen ervaren lesgever",
    "week_conflict": "Meerdere lessen in dezelfde week",
    "boven_richtlijn": "Boven de richtlijn ingedeeld",
    "onder_richtlijn": "Onder de richtlijn ingedeeld",
    "wijziging": "Bestaande toewijzing losgelaten",
}


@dataclass
class Uitleg:
    """Eén regel uitleg bij een les of lesgever: wat droeg bij aan de score, en hoeveel."""
    categorie: str
    tekst: str
    bijdrage: float
    les_id: str | None = None
    lesgever_id: str | None = None


@dataclass
class _Term:
    categorie: str
    coefficient: float
    var: object  # cp_model BoolVar/IntVar/LinearExpr, of een int/float-constante
    les_id: str | None
    lesgever_id: str | None


class TermCollector:
    def __init__(self) -> None:
        self._termen: list[_Term] = []

    def add(
        self,
        categorie: str,
        coefficient: float,
        var: object,
        *,
        les_id: str | None = None,
        lesgever_id: str | None = None,
    ) -> None:
        self._termen.append(_Term(categorie, coefficient, var, les_id, lesgever_id))

    def objective_terms(self) -> list:
        return [t.coefficient * t.var for t in self._termen]

    def breakdown(self, solver) -> dict[str, float]:
        """Som van bijdrages per categorie, na het oplossen."""
        resultaat: dict[str, float] = {}
        for t in self._termen:
            bijdrage = t.coefficient * solver.Value(t.var)
            resultaat[t.categorie] = resultaat.get(t.categorie, 0.0) + bijdrage
        return resultaat

    def per_les(self, solver) -> dict[str, list[Uitleg]]:
        """Niet-nul bijdrages gegroepeerd per les. Alleen termen die aan een specifieke les
        hangen (tekort/bezetting_bonus/misschien/geen_ervaren/wijziging) -- week-conflict en
        boven/onder-richtlijn zijn eigenschappen van een lesgever over meerdere lessen heen
        en horen thuis in een per-persoon-weergave (docs/PLAN.md fase 5), niet hier."""
        resultaat: dict[str, list[Uitleg]] = {}
        for t in self._termen:
            if t.les_id is None:
                continue
            bijdrage = t.coefficient * solver.Value(t.var)
            if bijdrage == 0:
                continue
            resultaat.setdefault(t.les_id, []).append(
                Uitleg(
                    categorie=t.categorie,
                    tekst=CATEGORIE_LABELS.get(t.categorie, t.categorie),
                    bijdrage=bijdrage,
                    les_id=t.les_id,
                    lesgever_id=t.lesgever_id,
                )
            )
        return resultaat
