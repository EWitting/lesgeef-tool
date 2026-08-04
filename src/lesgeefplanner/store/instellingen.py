"""Applicatie-instellingen die NIET in een projectbestand horen (recente bestanden).
Zie docs/DESIGN.md §2.7: deze horen in %LOCALAPPDATA%/Lesgeefplanner, niet in het project.

`basis_map` is uitsluitend voor tests, zodat de echte gebruikersmap niet wordt aangeraakt."""
from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_dir

MAX_RECENTE_BESTANDEN = 8
APP_NAAM = "Lesgeefplanner"


def _standaard_map() -> Path:
    return Path(user_data_dir(APP_NAAM, appauthor=False))


def _instellingen_pad(basis_map: Path | None = None) -> Path:
    map_ = basis_map if basis_map is not None else _standaard_map()
    map_.mkdir(parents=True, exist_ok=True)
    return map_ / "instellingen.json"


def laad_recente_bestanden(basis_map: Path | None = None) -> list[str]:
    """Geeft de paden van recent geopende .lesplan-bestanden, nieuwste eerst. Bestanden die
    niet meer bestaan worden overgeslagen."""
    pad = _instellingen_pad(basis_map)
    if not pad.exists():
        return []
    try:
        data = json.loads(pad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [p for p in data.get("recente_bestanden", []) if Path(p).exists()]


def voeg_recent_bestand_toe(bestandspad: Path, basis_map: Path | None = None) -> None:
    bestaande = laad_recente_bestanden(basis_map)
    pad_str = str(Path(bestandspad).resolve())
    bestaande = [p for p in bestaande if p != pad_str]
    bestaande.insert(0, pad_str)
    bestaande = bestaande[:MAX_RECENTE_BESTANDEN]
    inhoud = json.dumps({"recente_bestanden": bestaande}, indent=2, ensure_ascii=False)
    _instellingen_pad(basis_map).write_text(inhoud, encoding="utf-8")
