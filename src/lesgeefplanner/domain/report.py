"""Rendert een lijst Bevindingen naar platte tekst, voor "Kopieer rapport" (bv. om in de
commissie-chat te plakken). De tekst is een VIEW op de bevindingen, niet de bron -- de
brondata blijft de gestructureerde `list[Bevinding]` (docs/DESIGN.md §5).

Dit is een vereenvoudiging ten opzichte van het oude src/report.py: geen aparte
"lesgever-verdeling"-sectie meer (dat is geen bevinding maar een statistiek en hoort thuis
in het balkdiagram van het inspectiepaneel, niet in een lijst problemen). Zie
docs/BESLISSINGEN.md fase 5."""
from __future__ import annotations

from .analysis import Bevinding

_ERNST_KOP = {"fout": "PROBLEMEN", "waarschuwing": "WAARSCHUWINGEN", "info": "INFO"}


def genereer_tekstrapport(bevindingen: list[Bevinding]) -> str:
    if not bevindingen:
        return "Geen bijzonderheden gevonden."

    regels: list[str] = []
    for ernst in ("fout", "waarschuwing", "info"):
        groep = [b for b in bevindingen if b.ernst == ernst]
        if not groep:
            continue
        regels.append(f"=== {_ERNST_KOP[ernst]} ({len(groep)}) ===")
        for b in groep:
            regels.append(f"- {b.titel}")
        regels.append("")

    return "\n".join(regels).rstrip()
