"""Completed instantiation of the models after parsing."""
from datetime import date
from pydantic import BaseModel
from .config import Seizoen


class Les(BaseModel):
    datum: date
    tijd: str
    naam: str | None = None
    lesgevers: list[str] | None = None
    gaat_door: bool = True
    seizoen: Seizoen | None = None

class Planning(BaseModel):
    lessen: list[Les]