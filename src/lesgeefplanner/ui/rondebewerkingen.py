"""Bewerkingen op beschikbaarheidsrondes: aanmaken en importresultaten verwerken. Net als
ui/lesbewerkingen.py: UI-onafhankelijke functies die via state.doc.muteer(...) muteren, zodat
ze met gewone pytest-tests te toetsen zijn zonder een browser nodig te hebben."""
from __future__ import annotations

from datetime import date, datetime

from ..domain.formatting import format_datum_lang, format_tijdvak
from ..exchange.types import ImportResultaat
from ..model.availability import Antwoord, Ronde, RondeVraag
from ..model.project import Project
from ..model.scope import Scope
from .state import state


def maak_ronde(naam: str, scope: Scope, peildatum: date) -> str:
    """Maakt een nieuwe ronde met één vraag per les die de scope raakt, gesorteerd op
    datum/tijd. Geeft het id van de nieuwe ronde terug."""
    assert state.doc is not None
    project = state.doc.project
    lessen_in_scope = sorted(
        (
            les
            for les in project.lessen
            if les.status == "gaat_door" and scope.bevat(les, peildatum)
        ),
        key=lambda l: (l.datum, l.begin_tijd),
    )
    vragen = [
        RondeVraag(
            index=i + 1,
            les_id=les.id,
            label=f"{format_datum_lang(les.datum)} {format_tijdvak(les.begin_tijd, les.eind_tijd)}",
        )
        for i, les in enumerate(lessen_in_scope)
    ]
    ronde = Ronde(naam=naam, aangemaakt_op=datetime.now(), scope=scope, vragen=vragen)
    with state.doc.muteer(f"Datumprikker '{naam}' aangemaakt"):
        state.doc.project.rondes.append(ronde)
    return ronde.id


def verwerk_importresultaat(
    resultaat: ImportResultaat, keuzes_naamproblemen: dict[str, str | None]
) -> int:
    """Verwerkt een ImportResultaat: voegt de al gekoppelde antwoorden toe, plus de
    antwoorden waarvan de gebruiker net een naamprobleem heeft opgelost.

    `keuzes_naamproblemen`: ruwe_naam -> gekozen lesgever_id, of None om die rij over te
    slaan. Een bestaand antwoord van dezelfde lesgever in deze ronde wordt vervangen (een
    nieuwe import is de meest recente stand). Geeft het aantal verwerkte antwoorden terug."""
    assert state.doc is not None
    project = state.doc.project
    ronde = next((r for r in project.rondes if r.id == resultaat.ronde_id), None)
    if ronde is None:
        return 0

    nieuwe_antwoorden: dict[str, Antwoord] = {}
    for ga in resultaat.gekoppelde_antwoorden:
        nieuwe_antwoorden[ga.lesgever_id] = Antwoord(
            lesgever_id=ga.lesgever_id, waarden=ga.waarden, ingevuld_op=ga.ingevuld_op,
            doet_mee=ga.doet_mee,
        )
    # (lesgever_id, ruwe_naam) van elke handmatig opgeloste naam -- na de mutatie hieronder
    # als alias op de lesgever onthouden (_leer_alias), zodat dezelfde afwijkende spelling
    # bij een volgende herupload niet opnieuw een keuze vraagt.
    opgeloste_namen: list[tuple[str, str]] = []
    for probleem in resultaat.naamproblemen:
        gekozen_id = keuzes_naamproblemen.get(probleem.ruwe_naam)
        if gekozen_id is None:
            continue
        nieuwe_antwoorden[gekozen_id] = Antwoord(
            lesgever_id=gekozen_id, waarden=probleem.waarden, ingevuld_op=probleem.ingevuld_op,
            doet_mee=probleem.doet_mee,
        )
        opgeloste_namen.append((gekozen_id, probleem.ruwe_naam))

    if not nieuwe_antwoorden:
        return 0

    with state.doc.muteer(f"Antwoorden geïmporteerd in '{ronde.naam}'"):
        actuele_ronde = next(
            r for r in state.doc.project.rondes if r.id == resultaat.ronde_id
        )
        overige = [
            a for a in actuele_ronde.antwoorden if a.lesgever_id not in nieuwe_antwoorden
        ]
        actuele_ronde.antwoorden = overige + list(nieuwe_antwoorden.values())
        for lesgever_id, ruwe_naam in opgeloste_namen:
            _leer_alias(state.doc.project, lesgever_id, ruwe_naam)

    return len(nieuwe_antwoorden)


def _leer_alias(project: Project, lesgever_id: str, ruwe_naam: str) -> None:
    """Onthoudt een handmatig gekozen naamkoppeling op de lesgever zelf (zie
    exchange/forms_import.py, dat `Lesgever.aliassen` als extra exacte-match gebruikt)."""
    lesgever = next((lg for lg in project.lesgevers if lg.id == lesgever_id), None)
    if lesgever is None or ruwe_naam == lesgever.naam or ruwe_naam in lesgever.aliassen:
        return
    lesgever.aliassen = lesgever.aliassen + [ruwe_naam]
