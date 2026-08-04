"""Kernentiteiten: Lesgever, Seizoen, WeekSlot, Les, Toewijzing, Herkomst.
Zie docs/DESIGN.md §3.2-3.4."""
from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ids import nieuw_id


class Lesgever(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=nieuw_id)
    naam: str
    ervaring_jaren: int = 0
    actief: bool = True
    email: str | None = None
    notitie: str = ""


class WeekSlot(BaseModel):
    """Eén terugkerend moment in de week, bv. woensdag 16:00-19:00."""
    model_config = ConfigDict(extra="forbid")

    dag: int = Field(ge=0, le=6)  # 0 = maandag ... 6 = zondag
    begin_tijd: time
    eind_tijd: time


class Seizoen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=nieuw_id)
    naam: str
    begin: date
    eind: date  # inclusief
    # None = gebruik project.weekrooster. Een lege lijst is een geldige, expliciete keuze
    # (bv. PKursus, dat geen regulier weekrooster heeft) en mag NIET verward worden met None.
    weekrooster: list[WeekSlot] | None = None


class Herkomst(BaseModel):
    """Waar een gegenereerde les vandaan komt. Ontbreekt bij handmatig toegevoegde lessen."""
    model_config = ConfigDict(extra="forbid")

    seizoen_id: str
    weekslot_index: int


class Toewijzing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesgever_id: str
    vast: bool = False
    bron: Literal["handmatig", "solver", "import"] = "handmatig"


class Les(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=nieuw_id)
    datum: date
    begin_tijd: time
    eind_tijd: time
    seizoen_id: str | None = None
    titel: str | None = None
    soort: Literal["regulier", "extra"] = "regulier"
    status: Literal["gaat_door", "vervallen"] = "gaat_door"
    vervallen_reden: str | None = None
    herkomst: Herkomst | None = None
    # Wordt automatisch True zodra de gebruiker deze les handmatig aanpast (titel, status,
    # tijd) of er toewijzingen op zet. Beschermt de les tegen het hergenereren van de kalender.
    beschermd: bool = False
    toewijzingen: list[Toewijzing] = []
    notitie: str = ""
