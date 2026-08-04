"""Genereert een Google Apps Script dat een beschikbaarheidsformulier aanmaakt. Zie
docs/DESIGN.md §4.5: dit vermijdt OAuth-configuratie volledig -- de gebruiker plakt het
script eenmalig op script.google.com en voert het uit.

De vraagtitels krijgen een '#{index}'-suffix. Dat is de ankering die import op POSITIE
mogelijk maakt (forms_import.py), ongeacht of iemand een vraag later herschikt of het label
een net iets ander formaat krijgt in de export."""
from __future__ import annotations

import json

from ..model.availability import Ronde
from ..model.entities import Lesgever


def genereer_apps_script(ronde: Ronde, lesgevers: list[Lesgever]) -> str:
    actieve_namen = [lg.naam for lg in lesgevers if lg.actief]
    vragen_gesorteerd = sorted(ronde.vragen, key=lambda v: v.index)
    vragen_json = json.dumps(
        [{"label": v.label, "index": v.index} for v in vragen_gesorteerd], ensure_ascii=False
    )
    namen_json = json.dumps(actieve_namen, ensure_ascii=False)
    titel_json = json.dumps(f"Beschikbaarheid: {ronde.naam}", ensure_ascii=False)

    return f"""\
function maakFormulier() {{
  var form = FormApp.create({titel_json});
  form.setDescription(
    "Vul per moment in of je kunt lesgeven. Dit formulier is automatisch " +
    "gegenereerd door Lesgeefplanner -- niet de vraagtitels aanpassen, " +
    "anders kan het antwoord niet meer gekoppeld worden."
  );

  var lesgevers = {namen_json};
  var naamVraag = form.addListItem();
  naamVraag.setTitle("Wie ben je?");
  naamVraag.setChoiceValues(lesgevers);
  naamVraag.setRequired(true);

  var vragen = {vragen_json};
  for (var i = 0; i < vragen.length; i++) {{
    var vraag = form.addMultipleChoiceItem();
    vraag.setTitle(vragen[i].label + " #" + vragen[i].index);
    vraag.setChoiceValues(["Ja", "Misschien", "Nee"]);
    vraag.setRequired(true);
  }}

  Logger.log("Formulier aangemaakt.");
  Logger.log("Bewerklink: " + form.getEditUrl());
  Logger.log("Deel deze link om te laten invullen: " + form.getPublishedUrl());
}}
"""


def genereer_labellijst(ronde: Ronde) -> str:
    """Kopieerbare lijst met vraagtitels, voor wie het script niet wil gebruiken en het
    formulier met de hand maakt. Bevat bewust de '#index'-suffix, zodat #n-koppeling bij
    import ook dan blijft werken."""
    vragen_gesorteerd = sorted(ronde.vragen, key=lambda v: v.index)
    return "\n".join(f"{v.label} #{v.index}" for v in vragen_gesorteerd)
