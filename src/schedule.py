import ortools.sat.python.cp_model as cp_model
from .config import RoosterConfig
from .models import Les, Lesgever, Planning

def schedule_lessons(planning: Planning, lesgevers: list[Lesgever], beschikbaarheid_datumprikker: dict[date, list[str]], config: RoosterConfig) -> Planning:
    """Optimaliseert rooster op basis van een aantal constraints, 
    vooral soft constraints, om rekening te houden met situaties waar een perfect rooster niet gemaakt kan worden.
    Gebruikt Google OR-Tools."""