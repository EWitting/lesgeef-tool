from src.parse import parse_planning
from src.config import PlanningConfig
from src.export import export_planning
from src.importer import import_datumprikker, import_lesgevers, import_planning, import_forms_datumprikker
from src.schedule import schedule_lessons
from src.config import RoosterConfig
from src.report import generate_report
import numpy as np

if __name__ == "__main__":
    # Manier 1: Parse planning uit YAML configuratie
    # planning_config = PlanningConfig.from_yaml_file("data/planning.yml")
    # planning = parse_planning(planning_config)
    
    # Manier 2: Import planning direct uit Excel bestand (alternatief)
    planning = import_planning("./data/Lesgeef Planning 2025-2026.xlsx", starting_year=2025)

    lesgevers_path = "./data/lesgevers.xlsx"
    lesgevers = import_lesgevers(lesgevers_path)

    form_datumprikker_path = "./data/Beschikbaarheid Naseizoen 2 2025 (Responses).xlsx"
    datumprikker = import_forms_datumprikker(form_datumprikker_path, planning.lessen, lesgevers)

    # Tijdelijk, haal beka 1 lessen uit datupmrikker
    # beka_lessen_idx = [idx for idx, les in enumerate(planning.lessen) if les.naam == "Beginnerskamp 1"]
    # datumprikker.lessen = [les for les in datumprikker.lessen if les.naam != "Beginnerskamp 1"]
    # nieuwe_beschikbaarheid = []
    # for rij in datumprikker.beschikbaarheid:
    #     nieuwe_rij = [waarde for i, waarde in enumerate(rij) if i not in beka_lessen_idx]
    #     nieuwe_beschikbaarheid.append(nieuwe_rij)
    # datumprikker.beschikbaarheid = nieuwe_beschikbaarheid

    print(f"Lesgevers die minimaal 1 keer kunnen: {(np.array(datumprikker.beschikbaarheid) != 'Nee').any(axis=1).sum()}")
    print(f"Lesgevers al ingevuld: {len(datumprikker.lesgevers_al_ingevuld)}")
    print(f"Lesgevers nog te vullen: {len(datumprikker.lesgevers_nog_te_vullen)}")

    rooster_config = RoosterConfig.from_yaml_file("./data/roosterconfig.yaml")
    schedule_lessons(datumprikker, rooster_config)

    # Genereer rapport
    rapport = generate_report(planning, datumprikker, rooster_config)
    print("\n" + "="*50)
    print("ROOSTER RAPPORT")
    print("="*50)
    print(rapport)

    output_path = "./data/planning.xlsx"
    export_planning(planning, output_path)