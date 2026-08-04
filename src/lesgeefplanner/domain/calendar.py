"""Kalender genereren en veilig hergenereren. Zie docs/DESIGN.md §4.1.

Lessen worden GEMATERIALISEERD in project.lessen -- het zijn de objecten die de gebruiker
bewerkt. Maar ze moeten opnieuw afgeleid kunnen worden als seizoensdatums of het weekrooster
wijzigen, zonder handwerk te wissen. Dat gebeurt in twee stappen:

1. `gewenste_lessen()` berekent puur welke reguliere lessen ER ZOUDEN MOETEN ZIJN, gegeven de
   huidige seizoenen en weekroosters. Dit raakt project.lessen niet aan.
2. `bereken_kalender_diff()` vergelijkt dat met wat er al in project.lessen staat en levert een
   diff op die de gebruiker moet bevestigen (`pas_kalender_diff_toe()`). Dit wordt NOOIT
   automatisch uitgevoerd."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Iterator

from ..model.entities import Herkomst, Les
from ..model.project import Project

LesSleutel = tuple[str, date, time]  # (seizoen_id, datum, begin_tijd)


@dataclass(frozen=True)
class GewensteLes:
    seizoen_id: str
    datum: date
    begin_tijd: time
    eind_tijd: time
    weekslot_index: int


def _weken(start: date, eind: date) -> Iterator[date]:
    """Rondt start af naar de maandag op/voor start, itereert over maandagen t/m eind."""
    huidige = start - timedelta(days=start.weekday())
    while huidige <= eind:
        yield huidige
        huidige += timedelta(days=7)


def gewenste_lessen(project: Project) -> dict[LesSleutel, GewensteLes]:
    """Berekent welke reguliere lessen zouden moeten bestaan, gegeven de seizoenen en
    weekroosters in het project. Muteert niets.

    Overlappende seizoenen: als twee seizoenen dezelfde (datum, begin_tijd) opleveren, hoort
    dat bij het EERSTE seizoen in project.seizoenen; het tweede genereert daar niets. Dit
    wordt gesignaleerd door domain.analysis (code 'seizoenen_overlappen'), niet hier."""
    resultaat: dict[LesSleutel, GewensteLes] = {}
    geclaimd: dict[tuple[date, time], str] = {}

    for seizoen in project.seizoenen:
        # Let op: een LEGE lijst is een geldige, expliciete keuze (bv. PKursus zonder
        # regulier weekrooster) en mag niet verward worden met "geen eigen weekrooster".
        rooster = (
            seizoen.weekrooster if seizoen.weekrooster is not None else project.weekrooster
        )

        for week_maandag in _weken(seizoen.begin, seizoen.eind):
            for idx, slot in enumerate(rooster):
                datum = week_maandag + timedelta(days=slot.dag)
                if not (seizoen.begin <= datum <= seizoen.eind):
                    continue

                tijd_sleutel = (datum, slot.begin_tijd)
                if tijd_sleutel in geclaimd:
                    continue  # hoort al bij een eerder seizoen

                geclaimd[tijd_sleutel] = seizoen.id
                sleutel = (seizoen.id, datum, slot.begin_tijd)
                resultaat[sleutel] = GewensteLes(
                    seizoen_id=seizoen.id,
                    datum=datum,
                    begin_tijd=slot.begin_tijd,
                    eind_tijd=slot.eind_tijd,
                    weekslot_index=idx,
                )

    return resultaat


@dataclass
class KalenderDiff:
    toe_te_voegen: list[Les] = field(default_factory=list)
    te_verwijderen: list[Les] = field(default_factory=list)  # veilig: geen werk erin
    conflicten: list[tuple[Les, str]] = field(default_factory=list)  # zou verdwijnen, heeft werk
    # Afwijking van docs/DESIGN.md §4.1 (zie docs/BESLISSINGEN.md): eind_tijd van een
    # bestaande, niet-beschermde les mag bijgewerkt worden als het weekrooster wijzigt zonder
    # de begintijd te raken. (les_id, nieuwe_eind_tijd)
    tijd_updates: list[tuple[str, time]] = field(default_factory=list)

    def is_leeg(self) -> bool:
        return not (
            self.toe_te_voegen or self.te_verwijderen or self.conflicten or self.tijd_updates
        )


def bereken_kalender_diff(project: Project) -> KalenderDiff:
    """Vergelijkt gewenste_lessen() met de bestaande reguliere, gegenereerde lessen in het
    project. Extra lessen en handmatig toegevoegde lessen (herkomst is None) worden NOOIT
    aangeraakt."""
    gewenst = gewenste_lessen(project)

    bestaand: dict[LesSleutel, Les] = {}
    for les in project.lessen:
        if les.soort == "regulier" and les.herkomst is not None:
            sleutel = (les.herkomst.seizoen_id, les.datum, les.begin_tijd)
            bestaand[sleutel] = les

    diff = KalenderDiff()

    for sleutel, gw in gewenst.items():
        les = bestaand.get(sleutel)
        if les is None:
            diff.toe_te_voegen.append(
                Les(
                    datum=gw.datum,
                    begin_tijd=gw.begin_tijd,
                    eind_tijd=gw.eind_tijd,
                    seizoen_id=gw.seizoen_id,
                    herkomst=Herkomst(
                        seizoen_id=gw.seizoen_id, weekslot_index=gw.weekslot_index
                    ),
                )
            )
        elif not les.beschermd and les.eind_tijd != gw.eind_tijd:
            diff.tijd_updates.append((les.id, gw.eind_tijd))

    gewenst_sleutels = set(gewenst.keys())
    for sleutel, les in bestaand.items():
        if sleutel in gewenst_sleutels:
            continue
        if les.toewijzingen or les.beschermd:
            reden = "heeft toewijzingen" if les.toewijzingen else "is handmatig aangepast"
            diff.conflicten.append((les, reden))
        else:
            diff.te_verwijderen.append(les)

    return diff


def pas_kalender_diff_toe(project: Project, diff: KalenderDiff, geaccepteerd: set[str]) -> None:
    """Past alleen de aangevinkte regels toe. `geaccepteerd` bevat les-ids: voor
    toe_te_voegen en tijd_updates het (al aangemaakte) les.id, voor te_verwijderen en
    conflicten het id van de te verwijderen les. Roep dit aan binnen een `doc.muteer(...)`
    blok -- deze functie zelf beslist niets over undo."""
    for les in diff.toe_te_voegen:
        if les.id in geaccepteerd:
            project.lessen.append(les)

    te_verwijderen_ids = {les.id for les in diff.te_verwijderen if les.id in geaccepteerd}
    te_verwijderen_ids |= {les.id for les, _ in diff.conflicten if les.id in geaccepteerd}
    if te_verwijderen_ids:
        project.lessen = [l for l in project.lessen if l.id not in te_verwijderen_ids]

    if diff.tijd_updates:
        nieuwe_eindtijden = {
            les_id: eind for les_id, eind in diff.tijd_updates if les_id in geaccepteerd
        }
        if nieuwe_eindtijden:
            for les in project.lessen:
                if les.id in nieuwe_eindtijden:
                    les.eind_tijd = nieuwe_eindtijden[les.id]
