"""Document: bezit het Project, de undo-stack en het bestandspad. Zie docs/DESIGN.md §4.6.

`muteer()` is de ENIGE manier waarop het project mag veranderen. Alle UI-code en alle
exchange/planner-aanroepen die het project wijzigen, doen dat binnen een `with doc.muteer(...)`
blok. Dat garandeert dat undo/redo, de wijzigingsmarkering en autosave altijd kloppen."""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time as time_module
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..model.project import Project
from .migrations import migreer

MAX_UNDO = 50
BACKUP_MAP_NAAM = ".lesgeefplanner-backups"
MAX_BACKUPS = 10
AUTOSAVE_INTERVAL_SECONDEN = 30.0


class Document:
    def __init__(self, project: Project, pad: Path | None = None) -> None:
        self.project = project
        self.pad: Path | None = pad
        self._undo_stack: list[tuple[str, str]] = []  # (beschrijving, json-snapshot)
        self._redo_stack: list[tuple[str, str]] = []
        self._gewijzigd_sinds_opslaan = False
        self._laatste_wijziging: float | None = None

    # ------------------------------------------------------------------
    # Aanmaken / openen / opslaan
    # ------------------------------------------------------------------

    @classmethod
    def nieuw(cls, naam: str) -> "Document":
        return cls(Project(naam=naam))

    @classmethod
    def open(cls, pad: Path) -> "Document":
        ruw = json.loads(Path(pad).read_text(encoding="utf-8"))
        ruw = migreer(ruw)
        project = Project.model_validate(ruw)
        return cls(project, pad=pad)

    def opslaan(self, pad: Path | None = None) -> None:
        doel = Path(pad) if pad is not None else self.pad
        if doel is None:
            raise ValueError("Geen pad om naar op te slaan. Geef eerst een pad op.")

        inhoud = self.project.model_dump_json(indent=2)
        _schrijf_atomisch(doel, inhoud)
        self.pad = doel
        self._gewijzigd_sinds_opslaan = False
        self._laatste_wijziging = None
        _maak_backup(doel, inhoud)

    # ------------------------------------------------------------------
    # Muteren, undo, redo
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def muteer(self, beschrijving: str) -> Iterator[Project]:
        """Maakt vooraf een snapshot, voert het blok uit, en duwt de snapshot pas na
        succesvolle uitvoering op de undo-stack. Bij een uitzondering in het blok blijft
        het project ongewijzigd op de stack (de wijziging zelf is dan al toegepast op
        self.project -- roep dit alleen aan rond code die zelf geen state elders muteert)."""
        snapshot = self.project.model_dump_json()
        yield self.project
        self._undo_stack.append((beschrijving, snapshot))
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._gewijzigd_sinds_opslaan = True
        self._laatste_wijziging = time_module.monotonic()

    def ongedaan_maken(self) -> str | None:
        """Maakt de laatste mutatie ongedaan. Geeft de beschrijving terug, of None als er
        niets is om ongedaan te maken."""
        if not self._undo_stack:
            return None
        beschrijving, snapshot = self._undo_stack.pop()
        huidige_snapshot = self.project.model_dump_json()
        self._redo_stack.append((beschrijving, huidige_snapshot))
        self.project = Project.model_validate_json(snapshot)
        self._gewijzigd_sinds_opslaan = True
        self._laatste_wijziging = time_module.monotonic()
        return beschrijving

    def opnieuw(self) -> str | None:
        """Herhaalt de laatst ongedaan gemaakte mutatie. Geeft de beschrijving terug, of
        None als er niets is om te herhalen."""
        if not self._redo_stack:
            return None
        beschrijving, snapshot = self._redo_stack.pop()
        huidige_snapshot = self.project.model_dump_json()
        self._undo_stack.append((beschrijving, huidige_snapshot))
        self.project = Project.model_validate_json(snapshot)
        self._gewijzigd_sinds_opslaan = True
        self._laatste_wijziging = time_module.monotonic()
        return beschrijving

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def gewijzigd(self) -> bool:
        return self._gewijzigd_sinds_opslaan

    def kan_ongedaan_maken(self) -> bool:
        return bool(self._undo_stack)

    def kan_opnieuw(self) -> bool:
        return bool(self._redo_stack)

    def volgende_undo_beschrijving(self) -> str | None:
        """Beschrijving van de mutatie die `ongedaan_maken()` zou ongedaan maken, zonder de
        stack te wijzigen. Voor tooltips."""
        return self._undo_stack[-1][0] if self._undo_stack else None

    def volgende_redo_beschrijving(self) -> str | None:
        return self._redo_stack[-1][0] if self._redo_stack else None

    def autosave_indien_nodig(
        self, interval_seconden: float = AUTOSAVE_INTERVAL_SECONDEN
    ) -> bool:
        """Slaat op als er een pad bekend is, er niet-opgeslagen wijzigingen zijn, en de
        laatste wijziging minstens `interval_seconden` geleden is (debounce: niet opslaan
        tijdens actief typen/klikken). Geeft terug of er is opgeslagen."""
        if self.pad is None or not self._gewijzigd_sinds_opslaan:
            return False
        if self._laatste_wijziging is None:
            return False
        if time_module.monotonic() - self._laatste_wijziging < interval_seconden:
            return False
        self.opslaan()
        return True


def _schrijf_atomisch(doel: Path, inhoud: str) -> None:
    doel = Path(doel)
    doel.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_naam = tempfile.mkstemp(
        dir=doel.parent, prefix=f".{doel.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhoud)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_naam, doel)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_naam)
        raise


def _maak_backup(doel: Path, inhoud: str) -> None:
    backup_map = doel.parent / BACKUP_MAP_NAAM
    backup_map.mkdir(parents=True, exist_ok=True)
    tijdstempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_pad = backup_map / f"{doel.stem}-{tijdstempel}{doel.suffix}"
    backup_pad.write_text(inhoud, encoding="utf-8")

    bestaande = sorted(
        backup_map.glob(f"{doel.stem}-*{doel.suffix}"), key=lambda p: p.stat().st_mtime
    )
    for oud in bestaande[:-MAX_BACKUPS]:
        with contextlib.suppress(FileNotFoundError):
            oud.unlink()
