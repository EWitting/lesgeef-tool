"""Beschikbaarheidsrondes. Zie docs/DESIGN.md §3.5.

Bewust GEEN positionele matrix (les-index x lesgever-index) zoals de oude code, want die
breekt zodra er een les bijkomt of afgaat. Alles koppelt op id."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ids import nieuw_id
from .scope import Scope

Antwoordwaarde = Literal["ja", "misschien", "nee"]


class RondeVraag(BaseModel):
    """Eén vraag in het formulier, vastgelegd op het moment dat de ronde is aangemaakt.
    Dit maakt import op positie (#index) mogelijk, ongeacht latere labelwijzigingen."""
    model_config = ConfigDict(extra="forbid")

    index: int  # volgorde in het formulier, 1-based
    les_id: str
    label: str  # exact het label dat in het formulier is gezet


class Antwoord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesgever_id: str
    ingevuld_op: datetime | None = None
    doet_mee: bool = True  # uit de (nog niet geïmplementeerde) screeningvraag
    # les_id -> waarde. Een ONTBREKENDE les_id betekent "onbekend", niet "nee" -- dat
    # onderscheid is echt: niet gereageerd is iets anders dan niet kunnen.
    waarden: dict[str, Antwoordwaarde] = {}


class Ronde(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=nieuw_id)
    naam: str
    aangemaakt_op: datetime
    scope: Scope
    bron: Literal["google_forms", "datumprikker", "handmatig"] = "google_forms"
    vragen: list[RondeVraag] = []
    antwoorden: list[Antwoord] = []
