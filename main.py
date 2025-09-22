from src.parse import parse_planning
from src.config import PlanningConfig
from src.export import export_planning
from src.importer import import_datumprikker, import_lesgevers, import_planning
from src.schedule import schedule_lessons
from src.config import RoosterConfig

if __name__ == "__main__":
    # Manier 1: Parse planning uit YAML configuratie
    # planning_config = PlanningConfig.from_yaml_file("data/planning.yml")
    # planning = parse_planning(planning_config)
    
    # Manier 2: Import planning direct uit Excel bestand (alternatief)
    planning = import_planning("./data/Lesgeef Planning 2025-2026.xlsx", starting_year=2025)

    lesgevers_path = "./data/lesgevers.xlsx"
    lesgevers = import_lesgevers(lesgevers_path)

    # datumprikker_path = "./data/dapri.xlsx"
    # datumprikker = import_datumprikker(datumprikker_path, planning.lessen, lesgevers)

    # rooster_config = RoosterConfig.from_yaml_file("./data/roosterconfig.yaml")
    # schedule_lessons(datumprikker, rooster_config)

    output_path = "./data/planning.xlsx"
    export_planning(planning, output_path)