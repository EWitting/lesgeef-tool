"""Het projectdocument: alles wat in een .lesplan-bestand staat. Zie docs/DESIGN.md §3.1."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .config import SolverConfig
from .entities import Les, Lesgever, Seizoen, WeekSlot
from .availability import Ronde
from .scope import Scope
from .ids import nieuw_id

SCHEMA_VERSION = 2  # 2: Lesgever.ervaring_jaren (int) -> ervaren (bool), zie migrations.py


class Werkblad(BaseModel):
    """UI-state die je bewust wilt bewaren, zodat je bij heropenen terugkomt waar je was."""
    model_config = ConfigDict(extra="forbid")

    laatste_scope: Scope = Field(default_factory=Scope)
    peildatum_override: date | None = None
    laatste_export_pad: str | None = None


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    id: str = Field(default_factory=nieuw_id)
    naam: str
    seizoenen: list[Seizoen] = []
    weekrooster: list[WeekSlot] = []
    lesgevers: list[Lesgever] = []
    lessen: list[Les] = []
    rondes: list[Ronde] = []
    solver_config: SolverConfig = Field(default_factory=SolverConfig)
    werkblad: Werkblad = Field(default_factory=Werkblad)
