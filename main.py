from src.parse import parse_planning
from src.config import PlanningConfig
from src.export import export_planning
from src.importer import import_datumprikker, import_lesgevers

if __name__ == "__main__":
    planning_config = PlanningConfig.from_yaml_file("data/planning.yml")
    planning = parse_planning(planning_config)

    output_path = "./data/planning.xlsx"
    export_planning(planning, output_path)

    lesgevers_path = "./data/lesgevers.xlsx"
    lesgevers = import_lesgevers(lesgevers_path)

    datumprikker_path = "./data/dapri.xlsx"
    datumprikker = import_datumprikker(datumprikker_path, planning.lessen, lesgevers)

    print(datumprikker)