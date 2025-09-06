from src.parse import parse_planning
from src.config import PlanningConfig

if __name__ == "__main__":
    planning_config = PlanningConfig.from_yaml_file("data/planning.yml")
    planning = parse_planning(planning_config)
    for les in planning.lessen:
        print(les.seizoen.naam,les.datum, les.tijd, les.naam)