"""Shared application state bridging the UI to core src/ modules."""
from __future__ import annotations

import shutil
import traceback
from pathlib import Path
from typing import Callable

from src.config import PlanningConfig, RoosterConfig
from src.export import export_planning
from src.importer import import_forms_datumprikker, import_lesgevers, import_planning
from src.models import DatumPrikker, Lesgever, Les, Planning
from src.parse import parse_planning
from src.report import generate_report, vind_beschikaarheid
from src.schedule import schedule_lessons

DATA_DIR = Path("data")
PLANNING_YAML_PATH = DATA_DIR / "planning.yml"
ROOSTER_CONFIG_PATH = DATA_DIR / "roosterconfig.yaml"
LESGEVERS_XLSX_PATH = DATA_DIR / "lesgevers.xlsx"
OUTPUT_XLSX_PATH = DATA_DIR / "planning.xlsx"


class AppState:
    """Singleton-ish application state.  One instance is shared across the UI."""

    def __init__(self) -> None:
        self.planning: Planning | None = None
        self.lesgevers: list[Lesgever] | None = None
        self.datumprikker: DatumPrikker | None = None
        self.rooster_config: RoosterConfig = RoosterConfig()
        self.report_text: str = ""

        self._on_change_callbacks: list[Callable[[], None]] = []
        self._try_load_defaults()

    def _try_load_defaults(self) -> None:
        """Best-effort load of files that already exist on disk."""
        if PLANNING_YAML_PATH.exists():
            try:
                self.load_planning_from_yaml(PLANNING_YAML_PATH)
            except Exception:
                pass
        if ROOSTER_CONFIG_PATH.exists():
            try:
                self.rooster_config = RoosterConfig.from_yaml_file(ROOSTER_CONFIG_PATH)
            except Exception:
                pass
        if LESGEVERS_XLSX_PATH.exists():
            try:
                self.lesgevers = import_lesgevers(str(LESGEVERS_XLSX_PATH))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def load_planning_from_yaml(self, path: str | Path) -> None:
        config = PlanningConfig.from_yaml_file(path)
        self.planning = parse_planning(config)
        self._notify()

    def load_planning_from_yaml_string(self, text: str) -> None:
        config = PlanningConfig.from_yaml_string(text)
        self.planning = parse_planning(config)
        self._notify()

    def load_planning_from_excel(self, path: str | Path, starting_year: int = 2025) -> None:
        self.planning = import_planning(str(path), starting_year=starting_year)
        self._notify()

    def load_lesgevers(self, path: str | Path) -> None:
        self.lesgevers = import_lesgevers(str(path))
        self._notify()

    def load_datumprikker(self, path: str | Path) -> None:
        if self.planning is None:
            raise RuntimeError("Planning moet eerst geladen worden voordat de datumprikker kan worden geïmporteerd.")
        if self.lesgevers is None:
            raise RuntimeError("Lesgevers moeten eerst geladen worden voordat de datumprikker kan worden geïmporteerd.")
        self.datumprikker = import_forms_datumprikker(str(path), self.planning.lessen, self.lesgevers)
        self._notify()

    def run_scheduler(self) -> None:
        if self.datumprikker is None:
            raise RuntimeError("Datumprikker moet eerst geladen worden.")
        schedule_lessons(self.datumprikker, self.rooster_config)
        self._notify()

    def refresh_report(self) -> str:
        if self.planning is None or self.datumprikker is None:
            self.report_text = ""
            return self.report_text
        self.report_text = generate_report(self.planning, self.datumprikker, self.rooster_config)
        return self.report_text

    def export(self, path: str | Path | None = None) -> Path:
        if self.planning is None:
            raise RuntimeError("Geen planning om te exporteren.")
        out = Path(path) if path else OUTPUT_XLSX_PATH
        export_planning(self.planning, str(out))
        return out

    def save_rooster_config(self) -> None:
        """Persist the current rooster_config back to YAML."""
        import yaml
        data = self.rooster_config.model_dump()
        with open(ROOSTER_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def save_planning_yaml(self, text: str) -> None:
        """Write raw YAML text to planning.yml on disk."""
        PLANNING_YAML_PATH.write_text(text, encoding="utf-8")

    def save_uploaded_file(self, target: Path, content: bytes) -> None:
        target.write_bytes(content)

    # ------------------------------------------------------------------
    # Query helpers used by the UI
    # ------------------------------------------------------------------

    def get_availability_for_lesson(self, les: Les) -> list[tuple[Lesgever, str]]:
        """Return [(lesgever, 'Ja'|'Misschien'|'Nee'), ...] for a given lesson."""
        if self.datumprikker is None:
            return []
        results: list[tuple[Lesgever, str]] = []
        for lg in self.datumprikker.lesgevers_al_ingevuld:
            b = vind_beschikaarheid(self.datumprikker, lg, les)
            if b is not None:
                results.append((lg, b))
        return results

    def get_available_lesgevers_for_lesson(self, les: Les) -> list[tuple[Lesgever, str]]:
        """Return lesgevers sorted: Ja first, then Misschien. Nee excluded."""
        avail = self.get_availability_for_lesson(les)
        ja = [(lg, b) for lg, b in avail if b == "Ja"]
        misschien = [(lg, b) for lg, b in avail if b == "Misschien"]
        return ja + misschien

    # ------------------------------------------------------------------
    # Change notification
    # ------------------------------------------------------------------

    def on_change(self, callback: Callable[[], None]) -> None:
        self._on_change_callbacks.append(callback)

    def _notify(self) -> None:
        for cb in self._on_change_callbacks:
            try:
                cb()
            except Exception:
                traceback.print_exc()


state = AppState()
