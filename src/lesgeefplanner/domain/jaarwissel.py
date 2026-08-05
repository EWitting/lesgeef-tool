"""Rolt een bestaand project door naar een nieuw seizoen: rooster en lesgevers blijven
(iedereen wordt gemarkeerd als ervaren), toewijzingen/rondes worden leeggemaakt,
kalenderdatums schuiven op. Zie docs/PLAN.md fase 9 ("Nieuw jaar op basis van vorig
bestand")."""
from __future__ import annotations

from datetime import timedelta

from ..model.entities import Les, Seizoen
from ..model.project import Project

# 52 weken = 364 dagen: schuift de kalender ~1 jaar op MET behoud van de dag-van-de-week,
# zodat een 'woensdagavond'-activiteit weer op een woensdag valt. Een gewoon jaar (365/366
# dagen) zou dat verschuiven.
STANDAARD_VERSCHUIVING_DAGEN = 364


def rol_project_door(
    oud: Project, nieuwe_naam: str, dagen_verschuiving: int = STANDAARD_VERSCHUIVING_DAGEN
) -> Project:
    """Reguliere (gegenereerde) lessen worden NIET meegenomen -- die maakt 'Kalender
    bijwerken' opnieuw aan met de verschoven seizoensdata. Extra lessen worden wel
    meegenomen (met opgeschoven datum), toewijzingen/status/titel van oude lessen niet."""
    nieuw = Project(naam=nieuwe_naam)
    nieuw.weekrooster = [slot.model_copy() for slot in oud.weekrooster]
    nieuw.solver_config = oud.solver_config.model_copy()

    verschuiving = timedelta(days=dagen_verschuiving)
    seizoen_id_map: dict[str, str] = {}
    for seizoen in oud.seizoenen:
        nieuw_seizoen = Seizoen(
            naam=seizoen.naam,
            begin=seizoen.begin + verschuiving,
            eind=seizoen.eind + verschuiving,
            weekrooster=(
                [slot.model_copy() for slot in seizoen.weekrooster]
                if seizoen.weekrooster is not None
                else None
            ),
        )
        seizoen_id_map[seizoen.id] = nieuw_seizoen.id
        nieuw.seizoenen.append(nieuw_seizoen)

    for lesgever in oud.lesgevers:
        # Id blijft bewust hetzelfde -- dit is dezelfde persoon, en toekomstige koppelingen
        # (bv. Excel Code-kolommen, rondes) moeten voor dezelfde lesgever blijven werken.
        # Iedereen die een heel seizoen heeft meegedraaid, is nu ervaren (dit was vroeger
        # een "+1 jaar", maar de solver/analyse keken toch alleen naar >=1 jaar).
        nieuw.lesgevers.append(lesgever.model_copy(update={"ervaren": True}))

    for les in oud.lessen:
        if les.soort != "extra":
            continue
        nieuwe_seizoen_id = seizoen_id_map.get(les.seizoen_id) if les.seizoen_id else None
        nieuw.lessen.append(
            Les(
                datum=les.datum + verschuiving,
                begin_tijd=les.begin_tijd, eind_tijd=les.eind_tijd,
                seizoen_id=nieuwe_seizoen_id, titel=les.titel,
                soort="extra", beschermd=True,
            )
        )

    return nieuw
