"""Completed instantiation of the models after parsing."""
from datetime import date
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

    def id(self) -> str:
        import locale
        locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')
        # Use %d and then strip leading zero to be cross-platform compatible
        day_str = self.datum.strftime('%d').lstrip('0')
        return f"{self.datum.strftime('%a')} {day_str} {self.datum.strftime('%b %Y')} {self.tijd}".replace(" ", "")

class Planning(BaseModel):
    lessen: list[Les]

class DatumPrikker(BaseModel):
    lesgevers_al_ingevuld: list[Lesgever]
    lesgevers_nog_te_vullen: list[Lesgever]
    lessen: list[Les]

    # Matrix met Ja/Misschien/Nee. 
    # Index is (lesgever, les), op de volgorde van de lists in dit data object
    beschikbaarheid: list[list[str]]