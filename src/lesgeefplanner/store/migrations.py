"""Schema-migraties voor .lesplan-bestanden.

Elke migratie is een functie die de rauwe dict van schema-versie N omzet naar N+1. Ze worden
achter elkaar toegepast tot de huidige SCHEMA_VERSION is bereikt. Op schema_version 1 is dit
nog leeg -- het staat klaar voor als het nodig wordt."""
from __future__ import annotations

from typing import Callable

from ..model.project import SCHEMA_VERSION

MIGRATIES: dict[int, Callable[[dict], dict]] = {
    # 1: _migreer_van_1_naar_2,
}


class OnbekendSchemaError(Exception):
    """Het bestand heeft een schema_version die deze versie van de app niet kent."""


def migreer(data: dict) -> dict:
    """Past migraties toe totdat data['schema_version'] == SCHEMA_VERSION.
    Muteert een kopie, niet het origineel."""
    huidige = dict(data)
    versie = huidige.get("schema_version", 1)

    if versie > SCHEMA_VERSION:
        raise OnbekendSchemaError(
            f"Dit bestand is gemaakt met een nieuwere versie van Lesgeefplanner "
            f"(schema {versie}, deze app kent tot en met schema {SCHEMA_VERSION}). "
            f"Werk de app bij voordat je dit bestand opent."
        )

    while versie < SCHEMA_VERSION:
        stap = MIGRATIES.get(versie)
        if stap is None:
            raise OnbekendSchemaError(
                f"Geen migratiepad gevonden van schema {versie} naar {versie + 1}."
            )
        huidige = stap(huidige)
        versie += 1
        huidige["schema_version"] = versie

    return huidige
