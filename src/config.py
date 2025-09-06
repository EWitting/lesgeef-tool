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
