
from datetime import date, timedelta
from typing import Generator
from .config import PlanningConfig
from .models import Planning, Les

DAG_TO_NUMBER = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}

def week_iterator(start_date: date, end_date: date) -> Generator[date, None, None]:
    """Rounds start_date down to the nearest Monday before, iterates over mondays until end_date inclusive."""
    current_date = start_date - timedelta(days=start_date.weekday())
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=7)

def parse_planning(planning_config: PlanningConfig) -> Planning:

    # Genereer lessen gedurende seizoenen
    lessen = []
    for seizoen in planning_config.seizoenen:
        # Neem jaarlijks rooster over als niet gegeven
        if seizoen.weekrooster is None:
            seizoen.weekrooster = planning_config.weekrooster
        
        # Itereer door weken in het seizoen
        for week_start in week_iterator(seizoen.begin, seizoen.eind):
            # Itereer door dagen in de week
            for dag in seizoen.weekrooster:
                datum = week_start + timedelta(days=DAG_TO_NUMBER[dag.dag])

                # Maak les aan als het inderdaad binnen de data valt
                if datum >= seizoen.begin and datum <= seizoen.eind:
                    les = Les(
                        datum=datum,
                        tijd=dag.tijd,
                        seizoen=seizoen)
                    lessen.append(les)

    # Activiteiten (alleen effect bij overlap met een (gewone) les)
    for activiteit in planning_config.activiteiten:
        for les in lessen:
            if les.datum == activiteit.datum:
                les.naam = activiteit.naam
                les.gaat_door = activiteit.les_gaat_door
                if activiteit.tijd:
                    les.tijd = activiteit.tijd
    
    # Voeg extra lessen toe, wordt bij een seizoen geplaatst indien overlap
    for extra_les in planning_config.extra_lessen:
        for dag in extra_les.dagen:

            # vindt matchend seizoen 
            les_seizoen = None
            for seizoen in planning_config.seizoenen:
                if dag.datum >= seizoen.begin and dag.datum <= seizoen.eind:
                    les_seizoen = seizoen

            les = Les(
                datum=dag.datum,
                tijd=dag.tijd,
                seizoen=les_seizoen,
                naam=extra_les.naam)
            lessen.append(les)
    

    # Sorteer lessen op datum en tijd
    lessen.sort(key=lambda x: (x.datum, x.tijd))

    return Planning(lessen=lessen)