"""Specifies configuration file input format"""
from datetime import date
from typing import List
import yaml
from pydantic import BaseModel, Field
from pathlib import Path


class WeekRoosterDag(BaseModel):
    dag: str
    tijd: str


class Seizoen(BaseModel):
    naam: str
    begin: date
    eind: date
    weekrooster: List[WeekRoosterDag] | None = None


class ExtraLesDag(BaseModel):
    datum: date
    tijd: str


class ExtraLes(BaseModel):
    naam: str
    dagen: List[ExtraLesDag]


class Activiteit(BaseModel):
    """Als het overlapt met een les, wordt de naam er bij geschreven,
    en de les eventueel afgelast of tijd aangepast.
    Heeft geen effect op extra lessen."""
    naam: str
    datum: date
    les_gaat_door: bool = Field(alias="les-gaat-door")
    tijd: str | None = None


class Lesgever(BaseModel):
    """Persoonlijke info, handmatig verzamelen, zorgvuldig mee om gaan. 
    Naam matchen met smoelenboek url. Naam wordt later gematched met datumprikker."""
    naam: str
    ervaring_jaren: int
    actief: bool # Op false zetten zodra nieuwe commissie bepaald is


class PlanningConfig(BaseModel):
    seizoenen: List[Seizoen]
    weekrooster: List[WeekRoosterDag]
    extra_lessen: List[ExtraLes] = Field(alias="extra-lessen")
    activiteiten: List[Activiteit]


    @classmethod
    def from_yaml_file(cls, yaml_path: str | Path) -> "PlanningConfig":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r', encoding='utf-8') as file:
            yaml_data = yaml.safe_load(file)
        return cls(**yaml_data)
    
    @classmethod
    def from_yaml_string(cls, yaml_string: str) -> "PlanningConfig":
        """Load configuration from YAML string."""
        yaml_data = yaml.safe_load(yaml_string)
        return cls(**yaml_data)

class RoosterConfig(BaseModel):
    penalty_lesgever_tekort: float = 10
    penalty_misschien: float = 8
    penalty_geen_ervaren_lesgever: float = 5
    penalty_meerdere_lessen_per_week: float = 8
    richtlijn_lessen_per_week: float = 0.5
    penalty_boven_richtlijn: float = 5
    penalty_verdeling_stappen: List[float] = [1, 2, 3, 4, 5]  # Quadratic growth: 1, 3, 6, 10, 15
    lesgever_minimum: int = 2
    lesgever_maximum: int = 3   
    lesgever_bonus: float = 3

    @classmethod
    def from_yaml_file(cls, yaml_path: str | Path) -> "RoosterConfig":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r', encoding='utf-8') as file:
            yaml_data = yaml.safe_load(file)
        return cls(**yaml_data)
