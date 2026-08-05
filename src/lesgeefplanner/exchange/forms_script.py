"""Genereert een Google Apps Script dat een beschikbaarheidsformulier aanmaakt. Zie
docs/DESIGN.md §4.5: dit vermijdt OAuth-configuratie volledig -- de gebruiker plakt het
script eenmalig op script.google.com en voert het uit.

Structuur (zie docs/BESLISSINGEN.md, "formulier-indeling"): naam (open tekst) en een
screeningvraag ("wil je deze lessenreeks lesgeven?") op pagina 1, die bij "Nee" meteen naar
het einde springt; bij "Ja" pas naar pagina 2 met ÉÉN keuzerooster-vraag (rij per les,
kolommen Ja/Misschien/Nee) i.p.v. een aparte vraag per les -- dat laatste was bij 20+
lessen onwerkbaar lang.

Koppeling bij import gebeurt op VOLGORDE, niet op een '#N'-suffix in de vraagtekst (zie
forms_import.py) -- dat is de bewuste keuze na feedback: geen zichtbare "#1"/"#2" meer in
het formulier, ten koste van robuustheid als iemand vragen herschikt. De volgorde in het
gegenereerde script (naam, screening, dan de rooster-rijen in `ronde.vragen`-volgorde) is
dus ook precies de volgorde die forms_import.py verwacht terug te vinden in de export."""
from __future__ import annotations

import json
from datetime import date

from ..domain.formatting import MAANDEN_NL
from ..model.availability import Ronde
from ..model.project import Project


def _dag_maand(d: date) -> str:
    return f"{d.day} {MAANDEN_NL[d.month - 1]}"


def genereer_apps_script(ronde: Ronde, project: Project) -> str:
    vragen_gesorteerd = sorted(ronde.vragen, key=lambda v: v.index)
    les_by_id = {les.id: les for les in project.lessen}

    eerste_les = les_by_id.get(vragen_gesorteerd[0].les_id) if vragen_gesorteerd else None
    laatste_les = les_by_id.get(vragen_gesorteerd[-1].les_id) if vragen_gesorteerd else None
    if eerste_les and laatste_les:
        screening_zin = (
            f"Wil je in de periode {_dag_maand(eerste_les.datum)} t/m "
            f"{_dag_maand(laatste_les.datum)} lesgeven?"
        )
    else:
        screening_zin = "Wil je deze lessenreeks lesgeven?"

    rijen_json = json.dumps([v.label for v in vragen_gesorteerd], ensure_ascii=False)
    screening_titel_json = json.dumps(screening_zin, ensure_ascii=False)
    titel_json = json.dumps(f"Beschikbaarheid: {ronde.naam}", ensure_ascii=False)

    return f"""\
// Dit script is automatisch gegenereerd door Lesgeefplanner. Verander de VOLGORDE van de
// vragen hieronder niet na het aanmaken van het formulier -- Lesgeefplanner koppelt
// antwoorden terug op basis van die volgorde (naam, dan de screeningvraag, dan de
// rooster-rijen in deze volgorde). De mensen die het formulier INVULLEN zien deze code niet, dus
// dit is puur voor jou als beheerder.
function maakFormulier() {{
  var form = FormApp.create({titel_json});

  var naamVraag = form.addTextItem();
  naamVraag.setTitle("Wat is je naam?");
  naamVraag.setRequired(true);

  var screeningVraag = form.addMultipleChoiceItem();
  screeningVraag.setTitle({screening_titel_json});
  var paginaBeschikbaarheid = form.addPageBreakItem();
  paginaBeschikbaarheid.setTitle("Beschikbaarheid");
  paginaBeschikbaarheid.setHelpText(
    "Vul hier vooral in wanneer je nog plek hebt in de agenda, dan gaan wij daarmee " +
    "puzzelen om te zorgen dat iedereen ongeveer even vaak wordt ingedeeld en het een " +
    "beetje gelijk verspreid is over de periode. 'Ja' invullen betekent dus niet dat je " +
    "elke keer moet lesgeven."
  );
  screeningVraag.setChoices([
    screeningVraag.createChoice("Ja natuurlijk!", paginaBeschikbaarheid),
    screeningVraag.createChoice("Nee", FormApp.PageNavigationType.SUBMIT)
  ]);
  screeningVraag.setRequired(true);

  var rijen = {rijen_json};
  if (rijen.length > 0) {{
    var rooster = form.addGridItem();
    rooster.setTitle("Kun je lesgeven op:");
    rooster.setRows(rijen);
    rooster.setColumns(["Ja", "Misschien", "Nee"]);
    rooster.setRequired(true);
  }}

  Logger.log("Formulier aangemaakt.");
  Logger.log("Bewerklink: " + form.getEditUrl());
  Logger.log("Deel deze link om te laten invullen: " + form.getPublishedUrl());
}}
"""


def genereer_labellijst(ronde: Ronde) -> str:
    """Kopieerbare lijst met vraagtitels, voor wie het script niet wil gebruiken en het
    formulier met de hand maakt (als rijen van een keuzerooster-vraag, in deze volgorde --
    zie forms_import.py: koppeling gebeurt op volgorde, niet op tekst)."""
    vragen_gesorteerd = sorted(ronde.vragen, key=lambda v: v.index)
    return "\n".join(v.label for v in vragen_gesorteerd)
