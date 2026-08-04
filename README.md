# Lesgeefplanner

Een tool voor het maken en beheren van de lesgeefplanning van een zeilcommissie (of
vergelijkbare vrijwilligersclub): seizoenen en een weekrooster instellen, beschikbaarheid
ophalen via Google Forms, automatisch een rooster laten voorstellen, en het resultaat delen
via Excel/Google Drive.

## Snel starten

1. **Installeer** de app: download de nieuwste `.exe` van de
   [Releases-pagina](../../releases) en dubbelklik hem. Er hoeft niets anders geïnstalleerd
   te worden. (Windows kan bij de eerste keer een waarschuwing tonen omdat het programma
   niet digitaal ondertekend is -- kies "Meer info" → "Toch uitvoeren".)
2. De app opent in een eigen venster. Kies **Nieuw project**, of **Nieuw jaar op basis van
   vorig bestand** als je het bestand van vorig jaar hebt.
3. Volg de stappen in het linkerpaneel: **Jaarplanning → Lesgevers → Beschikbaarheid →
   Inroosteren → Delen**. Elke stap heeft ✓ (klaar), ! (nog aandacht nodig) of — (nog niet
   begonnen) ervoor, zodat je in één oogopslag ziet wat er nog moet gebeuren.

Uitleg bij elke actie staat direct bij de knop in de app zelf (bijvoorbeeld de stappen om
een Google Form aan te maken staan naast de knop "Formulier maken" onder
Beschikbaarheid) -- dit README is dus bewust kort.

## Wat de stappen doen

- **Jaarplanning** -- seizoenen (begin/eind-datum) en een weekrooster (welke dag, welke
  tijd) instellen. De app rekent live uit hoeveel lessen dat oplevert. Met "Kalender
  bijwerken" genereer je de lessen; je krijgt eerst te zien wat er verandert voordat er
  iets wordt toegepast.
- **Lesgevers** -- de lijst met mensen die kunnen lesgeven, met hun ervaring. Kan met de
  hand ingevuld worden of geïmporteerd uit een Excel-bestand.
- **Beschikbaarheid** -- maak een ronde aan voor een seizoen; de app genereert een script
  waarmee in twee minuten een Google Form met alle lessen en een naam-keuzelijst klaarstaat.
  Antwoorden importeer je terug met hetzelfde paneel.
- **Inroosteren** -- gebeurt in het middenpaneel, dat altijd het rooster toont. Wijs met de
  hand lesgevers toe, of klik "Automatisch invullen" voor een voorstel (dat je per les kunt
  goed- of afkeuren voordat het wordt toegepast). Het rechterpaneel toont problemen
  (bijvoorbeeld te weinig lesgevers) en hoe de belasting verdeeld is.
- **Delen** -- exporteer naar Excel om te delen via Google Drive. Wijzigingen die daar
  direct worden gemaakt (bijvoorbeeld iemand die zelf zijn naam invult) kun je met dezelfde
  knop weer terughalen; de app laat per wijziging zien wat er anders is voordat het wordt
  toegepast.

## Het projectbestand

Alles staat in één `.lesplan`-bestand: seizoenen, rooster, lesgevers, beschikbaarheid en
het huidige rooster. Bewaar dit bestand ergens waar je opvolger er ook bij kan (bijvoorbeeld
de gedeelde Drive-map van de commissie) -- dat bestand is de volledige overdracht naar
volgend jaar.

## Problemen

Gaat er iets mis, dan toont de app een melding met een knop "Kopieer technische details".
Plak die in een bugreport. Details staan ook altijd in
`%LOCALAPPDATA%\Lesgeefplanner\log.txt`.

## Ontwikkelen

Dit project gebruikt [uv](https://docs.astral.sh/uv/). Vanuit de projectmap:

```sh
uv sync              # dependencies installeren
uv run lesgeefplanner  # de app starten
uv run pytest         # tests draaien
```

De architectuur en de belangrijkste ontwerpkeuzes staan in `docs/DESIGN.md`, het
uitvoeringsplan in `docs/PLAN.md`, en beslissingen die tijdens de bouw zijn gemaakt (met
reden) in `docs/BESLISSINGEN.md`.
