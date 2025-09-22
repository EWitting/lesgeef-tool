"""Completed instantiation of the models after parsing."""
from datetime import date, datetime
from pydantic import BaseModel
from .config import Seizoen

class Lesgever(BaseModel):
    naam: str
    ervaring_jaren: int
    actief: bool

class Les(BaseModel):
    datum: date
    tijd: str
    naam: str | None = None
    lesgevers: list[Lesgever] | None = None
    gaat_door: bool = True
    seizoen: Seizoen | None = None

    def datetime(self) -> datetime:
        # Gebruikt alleen de begintijd (ervan uitgaand dat tijd in het format HH:MM - HH:MM is)
        begin_tijd = self.tijd.split("-")[0].rstrip()
        return datetime.combine(self.datum, datetime.strptime(begin_tijd, "%H:%M").time())

class Planning(BaseModel):
    lessen: list[Les]

class DatumPrikker(BaseModel):
    lesgevers_al_ingevuld: list[Lesgever]
    lesgevers_nog_te_vullen: list[Lesgever]
    lessen: list[Les]

    # Matrix met Ja/Misschien/Nee. 
    # Index is (lesgever, les), op de volgorde van de lists in dit data object
    beschikbaarheid: list[list[str]]