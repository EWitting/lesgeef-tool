# Jaarplanning maken

* Maak een **planning.yml** bestand aan zoals hier onder. 
* **Seizoenen** zijn de periodes waarin de lessen plaatsvinden. Vooral handig om rooster datumprikker periodes uit elkaar te houden en winterstop e.d. te bepalen.
* **Weekrooster** is het standaard rooster waarin de lessen plaatsvinden. Dit wordt voor elk seizoen gebruikt, tenzij het seizoen zelf een `weekrooster` heeft.
* **Extra-lessen** zijn lessen die niet uit het normale rooster komen, zoals X-lessen, PKursus, open lessen etc.
* **Activiteiten** zijn alleen relevant als ze overlappen met een les. Ze kunnen ofwel de automatisch gegenereerde lessen zichtbaar aflassen met een reden (`les-gaat-door: false`), of gebruikt worden om de naam en eventueel tijd aan te passen (`les-gaat-door: true` en optioneel `tijd`). Ze hebben geen effect op *extra-lessen*.
```yaml
seizoenen:
  - naam: "Naseizoen 1"
    begin: "2025-09-01"
    eind: "2025-09-28"
  - naam: "Naseizoen 2"
    begin: "2025-10-01"
    eind: "2025-11-16"
  ...

weekrooster:
  - dag: "woensdag"
    tijd: "17:00 - 20:00"
  - dag: "zaterdag"
    tijd: "14:00 - 17:00"
  - dag: "zondag"
    tijd: "14:00 - 17:00"

extra-lessen:
  - naam: "Open Les"
    dagen:
      - datum: "2025-09-21"
        tijd: "10:00 - 13:00"
      - datum: "2025-09-28"
        tijd: "10:00 - 13:00"
    ...

activiteiten:
  - naam: "Robbie Games"
    datum: "2025-09-20"
    les-gaat-door: false
  - naam: "Lustrum Activiteit"
    datum: "2025-08-05"
    les-gaat-door: false
   ...
```

# Seizoen inroosteren

* **Maak een `Lesgevers` sheet** in een excel bestand met de namen van iedereen in de commissie (kan in hetzelfde bestand als de planning zijn). Dit is om ervaring bij te kunnen houden maar ook vooral om te kunnen zien wie nog ontbreekt in de datumprikker. Het moet tenminste kolommen `Naam`, `Ervaring`  en `Actief` hebben. Waarbij `Ervaring` bijvoorbeeld het aantal jaren exclusief de huidige is.

| Naam | Ervaring (jaren) | Actief |
|------|----------------|--------|
| Jan Jansen | 3 | true |
| Piet Peters | 2 | false |

* **Maak een datumprikker** aan, zorg (vanzelfsprekend) dat de data en tijden zo veel mogelijk overeen komen met de lessen in de planning voor een specifiek seizoen. Het wordt gemeld als er iets ontbreekt.
* **Exporteer de datumprikker naar excel**, update hem af en toe door opnieuw te downloaden zodra meer mensen het hebben ingevuld.
* (Optioneel) pas `rooster_config.yml` voor configuratie van het rooster algoritme.
