# Lesgeefplanner — Uitvoeringsplan

Volgorde en acceptatiecriteria voor de rewrite. **Lees eerst `docs/DESIGN.md` volledig.**
Dit plan verwijst er voortdurend naar; de moeilijke stukken staan daar uitgeschreven in §4.

Werk op branch `rewrite`. Commit per fase (of kleiner), met een Nederlandse commit message.
Fases zijn zo geordend dat de app na fase 3 al bruikbaar is en daarna nooit meer stukgaat.

**Regel voor wie dit uitvoert:** als je tijdens een fase een ontwerpkeuze moet maken die niet
in DESIGN.md staat, doe hem niet impliciet. Noteer hem in `docs/BESLISSINGEN.md` met datum en
reden, en ga door.

---

## Fase 0 — Skelet

**Doel:** de nieuwe pakketstructuur bestaat en start op, zonder gedragsverandering.

Taken:
1. Maak `src/lesgeefplanner/` met de mappenstructuur uit DESIGN.md §7. Alle `__init__.py`
   aanmaken, modules mogen leeg zijn.
2. `pyproject.toml`: voeg toe
   ```toml
   [project.scripts]
   lesgeefplanner = "lesgeefplanner.__main__:main"

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/lesgeefplanner"]
   ```
   Verwijder `ipykernel`, `matplotlib` en `scipy` uit de dependencies — die worden nergens
   gebruikt en `matplotlib` maakt de PyInstaller-bundel onnodig groot. Voeg `pytest` toe als
   dev-dependency.
3. `__main__.py`: `main()` die NiceGUI start op een **vrije poort** (niet hardgecodeerd 8080;
   zoek een vrije poort met een socket-bind op poort 0) en de browser opent.
4. `tests/` met één test die `import lesgeefplanner` doet.

**Klaar wanneer:** `uv run lesgeefplanner` opent een browser met een lege pagina en
`uv run pytest` slaagt.

---

## Fase 1 — Datamodel en documentopslag

**Doel:** een `.lesplan`-bestand kan aangemaakt, opgeslagen, geopend en gemuteerd worden.

Taken:
1. Implementeer alle modellen uit DESIGN.md §3 in `model/`. Gebruik
   `model_config = ConfigDict(extra="forbid")`. Ids via een helper `nieuw_id() -> str` in
   `model/__init__.py` (`uuid4().hex`).
2. `store/document.py` volgens DESIGN.md §4.6: `Document.nieuw/open/opslaan/muteer/
   ongedaan_maken/opnieuw`, atomisch schrijven, autosave, backupmap.
3. `store/migrations.py` met een lege `MIGRATIES: dict[int, Callable[[dict], dict]]` en een
   `migreer(data: dict) -> dict` die stapsgewijs ophoogt tot de huidige `schema_version` en een
   duidelijke fout geeft als het bestand nieuwer is dan de app.
4. `domain/formatting.py`: `DAGEN_NL`, `MAANDEN_NL`, `MAANDEN_NL_KORT`,
   `format_datum(d) -> "zondag 19 apr"`, `format_tijdvak(begin, eind) -> "14:00 - 17:00"`,
   `parse_nl_datum(s) -> date`. **Nul gebruik van `locale`.**

**Valkuilen:**
- `muteer()` moet de snapshot maken **vóór** het blok, niet erna.
- `os.replace()` (atomisch) gebruiken, niet `shutil.move()`.
- Een `time` in JSON serialiseert als `"14:00:00"`; laat pydantic dat doen, schrijf geen
  eigen encoder.

**Klaar wanneer:** tests dekken: nieuw → muteer → opslaan → openen geeft hetzelfde project;
undo herstelt exact; 51 mutaties laten de stack op 50 staan; een bestand met
`schema_version: 99` geeft een nette Nederlandse foutmelding.

---

## Fase 2 — Kalender genereren + planning tonen

**Doel:** je kunt een projectbestand openen en het rooster zien.

Taken:
1. `domain/calendar.py` volledig volgens DESIGN.md §4.1: `gewenste_lessen`,
   `bereken_kalender_diff`, `pas_kalender_diff_toe`.
2. `ui/app.py`: de drie-zone-layout uit DESIGN.md §2.6 — header (projectnaam,
   opgeslagen-indicator, scope, peildatum, undo/redo, exportmenu), inklapbare linkerrail,
   midden = planning (altijd), rechts = inspector (nu nog leeg).
3. `ui/planning_view.py`: `PlanningView` met `rebuild()` en `refresh_les()` volgens
   DESIGN.md §4.7. Per les één rij: datum, tijd, titel/status, `lesgever_maximum` slots,
   plaats voor een issue-stip. Groepeer op seizoen met een kopregel. Week-scheiding als
   bovenrand, wisselende achtergrond per even/oneven ISO-week (net als nu).
4. `ui/startscherm.py`: recente bestanden, "Nieuw", "Openen". Recente bestanden in
   `%LOCALAPPDATA%/Lesgeefplanner/instellingen.json` (gebruik `platformdirs`).

**Valkuilen:**
- Test `gewenste_lessen` expliciet met `weekrooster: []` (PKursus in de huidige
  `planning.yml`) — `if seizoen.weekrooster:` is fout, het moet `is not None` zijn.
- De week-iterator rondt af naar de maandag op/vóór `seizoen.begin`; lessen buiten
  `[begin, eind]` weglaten. Dit is dezelfde logica als het huidige `src/parse.py`, neem hem
  over.

**Klaar wanneer:** een handgeschreven testproject met 2 seizoenen toont het juiste aantal
lessen, in de juiste volgorde, en `bereken_kalender_diff` op een ongewijzigd project geeft
een lege diff.

---

## Fase 3 — Bewerken

**Doel:** de app is bruikbaar zonder solver. Alles wat je met de hand wilt doen, kan.

Taken:
1. Klik op een lesgeverslot → menu met alle lesgevers. Groepering op beschikbaarheid komt in
   fase 6; toon nu alfabetisch met hun huidige aantal lessen. Acties: toewijzen, 📌
   vastzetten/losmaken, ✕ wissen.
2. Rechtsklik (of ⋮-knop) op een les → *Vervalt…* (vraagt een reden), *Gaat weer door*,
   *Tijd aanpassen*, *Titel geven*, *Verwijderen* (alleen bij `soort="extra"`).
3. Klik op een lege dag in de kalender → *Extra les toevoegen* (datum, tijd, titel).
4. Elke bewerking loopt via `doc.muteer("<beschrijving>")` en roept daarna
   `refresh_les(les_id)` aan — plus de andere lessen in dezelfde ISO-week.
5. Undo/redo-knoppen in de header, met de beschrijving als tooltip. Sneltoetsen Ctrl+Z /
   Ctrl+Y.
6. Elke bewerking die een les inhoudelijk verandert zet `beschermd = True`.

**Valkuilen:**
- Toewijzingen die de gebruiker zelf zet krijgen `bron="handmatig"` en `vast=True`. De
  gebruiker die met de hand iemand neerzet, bedoelt dat.
- Roep nooit `rebuild()` aan na een celwijziging.

**Klaar wanneer:** je kunt een volledig rooster met de hand maken, afsluiten, heropenen en
alles staat er nog. Undo werkt over minstens 20 stappen.

---

## Fase 4 — Solver

**Doel:** automatisch invullen, veilig en uitlegbaar.

Taken:
1. `planner/terms.py`: `TermCollector` volgens DESIGN.md §4.2.
2. `planner/solve.py`: poort `src/schedule.py`. **Verander de penaltyformules niet** — die zijn
   getuned. Verander wél de drie punten uit DESIGN.md §4.2: weekconflicten tellen context mee,
   werkverdeling telt reeds gegeven lessen mee, en wijzigingskosten.
3. `planner/request.py` / `result.py`: `PlanRequest`, `PlanResult`, `Uitleg`.
4. Een `bouw_request(project, scope, peildatum) -> PlanRequest` helper in `planner/` die de
   scope-splitsing doet (`lessen_in_scope` versus `lessen_context`). Dit is de plek waar
   fouten insluipen — schrijf er een test voor.
5. UI: knop "Automatisch invullen". Draait in een executor (niet blokkerend), toont voortgang,
   en presenteert het resultaat via `dialogen/diff_dialoog.py` als voorstel:
   "12 lessen gewijzigd, 3 nieuw ingevuld, 1 persoon vervangen" met vinkjes per les.
   Pas alleen toe wat is aangevinkt, in één `doc.muteer("Automatisch ingevuld")`.
6. Bij `status == "onhaalbaar"`: Nederlandse uitleg, geen traceback. Bij
   `minimum_afgedwongen == False`: melden dat het minimum niet overal gehaald is.
7. Toegepaste solvertoewijzingen krijgen `vast=False`, `bron="solver"`.

**Valkuilen:**
- Alleen lesgevers met `actief=True` meegeven.
- Bij beschikbaarheid `"onbekend"` **geen** variabele aanmaken.
- `num_search_workers = 1` en `random_seed = 0`, anders geeft twee keer draaien twee
  verschillende antwoorden en lijkt de app onbetrouwbaar.
- Bij meerdere seizoenen in scope: `doel[g]` en `reeds[g]` per seizoen berekenen, niet
  gemengd.

**Klaar wanneer:** de tests uit DESIGN.md §8 voor `planner/` slagen, en op het echte
seizoensdata levert twee keer achter elkaar draaien exact hetzelfde rooster.

---

## Fase 5 — Analyse en inspectie

**Doel:** problemen zijn zichtbaar en aanklikbaar; de score is uitlegbaar.

Taken:
1. `domain/analysis.py`: `Bevinding` + `analyseer()` met alle codes uit DESIGN.md §5.
2. `domain/report.py`: render `list[Bevinding]` naar platte tekst in het formaat dat
   `src/report.py` nu produceert (zodat "kopieer voor de commissieapp" hetzelfde oplevert).
3. `ui/inspector.py`, drie standen:
   - **niets geselecteerd** → gezondheid van de scope: bevindingen gegroepeerd op ernst met
     telbadges, elk item klikbaar (scrolt naar de les/persoon en licht die 2 s op); daaronder
     het balkdiagram belasting-per-persoon met de doelband; daaronder "Waarom deze score?"
     met `PlanResult.verdeling` per categorie.
   - **les geselecteerd** → datum/tijd/status, wie beschikbaar is (Ja/Misschien/Onbekend/Nee),
     de bevindingen van die les, en de `Uitleg` uit het laatste `PlanResult`.
   - **persoon geselecteerd** → al hun lessen dit seizoen, hun belasting versus doel, hun
     beschikbaarheid.
4. Issue-stip per rij in `planning_view`: kleur naar hoogste ernst, tooltip met de titels.
5. Knop "Kopieer rapport".

**Valkuilen:**
- `analyseer()` moet snel genoeg zijn om na elke bewerking te draaien (< 50 ms bij 150 lessen).
  Geen geneste lussen over lessen × lesgevers × rondes; bouw eerst lookup-dicts.
- Het balkdiagram: gebruik NiceGUI's eigen elementen of een simpele gestileerde `div` per
  persoon. Trek `matplotlib` er niet weer bij.

**Klaar wanneer:** elk van de 12 bevindingscodes is met een testproject op te roepen, en
klikken op een bevinding brengt je bij het juiste object.

---

## Fase 6 — Beschikbaarheidsrondes

**Doel:** de Google Forms-flow is begeleid, en import is robuust.

Taken:
1. `exchange/types.py`: `ImportResultaat` (gekoppelde antwoorden, niet-gekoppelde kolommen,
   naamproblemen, waarschuwingen). Deel deze vorm alvast met de latere datumprikker-import.
2. `dialogen/rondes.py`: rondes aanmaken (naam + scope), overzicht van bestaande rondes.
3. `exchange/forms_script.py`: `genereer_apps_script()` volgens DESIGN.md §4.5. De UI toont
   het script in een kopieerblok met vier genummerde stappen ernaast, en een kopieerbare
   labellijst als handmatig alternatief.
4. `exchange/forms_import.py`: `lees_forms_export()` volgens DESIGN.md §4.5, inclusief de
   `#n`-koppeling, de terugval op labelparsing, lege cel = **onbekend**, en dubbele reacties.
5. `domain/names.py`: `stel_voor()` en `display_names()`. Resolutiewizard in de UI voor namen
   met `zekerheid="voorstel"`.
6. Responsoverzicht: wie heeft gereageerd, wie niet, knop "Kopieer lijst voor herinnering".
7. Beschikbaarheid zichtbaar maken in de planning: het lesgevermenu uit fase 3 groepeert nu op
   Ja / Misschien / Onbekend / Nee; "misschien" krijgt de gele celkleur zoals nu; een schakelaar
   "Toon beschikbaarheid" voegt kolommen per lesgever toe aan de planning-rijen.

**Valkuilen:**
- **Nooit** `fillna("Nee")`. Leeg is onbekend. Dit is een echt onderscheid, zie DESIGN.md §3.5.
- Het jaar komt uit `Ronde.scope` / de gekoppelde les, **nooit** uit de response-timestamp.
- De naamkolom moet ook werken als de dropdown is gebruikt (dan zijn het exacte matches en
  hoort de wizard niet te verschijnen).

**Klaar wanneer:** een echte forms-export van vorig seizoen importeert zonder handmatige
tussenkomst, en een export waarin één vraag is hernoemd importeert nog steeds correct via
`#n`.

---

## Fase 7 — Excel export en terug-import

**Doel:** de Drive-sheet werkt als tweerichtingsverkeer.

Taken:
1. `exchange/excel_export.py`: poort `src/export.py`, opmaak ongewijzigd, plus de `Code`-kolom
   en het verborgen `_meta`-blad uit DESIGN.md §4.3. `locale` eruit.
2. `exchange/excel_import.py`: `lees_sheet()` volgens DESIGN.md §4.4 met de drie
   koppelstrategieën en naamresolutie.
3. UI: "Exporteer Excel" (onthoudt het pad in `Werkblad.laatste_export_pad`) en
   "Lees wijzigingen uit Excel", die de `diff_dialoog` toont.
4. `exchange/roster_import.py`: lesgevers uit xlsx, met kolommapping-wizard in plaats van de
   harde `ValueError` die er nu is bij een ontbrekende kolom.

**Valkuilen:**
- Google Sheets kan datums en tijden herformatteren. Vertrouw daarom op `les_id`/`Code`, en
  gebruik datum+tijd alleen als laatste terugval.
- Toegepaste Excel-wijzigingen worden `vast=True, bron="import"`.
- Round-trip-test is verplicht (DESIGN.md §8).

**Klaar wanneer:** exporteren → een naam wijzigen in het bestand → importeren geeft precies
één `Wijziging`, en het `_meta`-blad verwijderen breekt de koppeling niet.

---

## Fase 8 — Jaarplanning-editor (de YAML verdwijnt)

**Doel:** het jaar is volledig in de UI op te zetten.

Taken:
1. `dialogen/jaarplanning.py`: seizoenen als tabel (naam, begin, eind, eigen weekrooster
   ja/nee) plus een tijdlijnstrook; weekrooster als "welke dag, welke tijd" met een live teller
   ("dit levert 34 lessen op").
2. Knop "Kalender bijwerken" → `bereken_kalender_diff` → `diff_dialoog`. Nooit automatisch.
3. `exchange/legacy_import.py` volgens DESIGN.md §6.1, met de waarschuwingenlijst.
4. Verwijder de YAML-editor uit de UI. Voeg in plaats daarvan onder "Geavanceerd" een
   **alleen-lezen** JSON-weergave van het project toe (handig bij debuggen).

**Klaar wanneer:** de huidige `data/planning.yml` importeert met precies de verwachte
waarschuwingen over Lustrum Trip en Vooka, en een nieuw jaar is van nul op te zetten zonder
ooit tekst te bewerken.

---

## Fase 9 — Begeleiding

**Doel:** iemand die de app nooit zag, komt er zelf uit.

Taken:
1. `ui/stappen.py`: linkerrail met de stappen — Jaarplanning, Lesgevers, Beschikbaarheid,
   Inroosteren, Delen — elk met ✓ / ! / — op basis van de projecttoestand. Klikken opent het
   bijbehorende paneel; het middenpaneel blijft altijd de planning.
2. Eerste-keer-scherm: "Nieuw jaar", "Nieuw jaar op basis van vorig bestand" (rol door: rooster
   overnemen, ervaring +1, toewijzingen en rondes leegmaken, kalenderdatums opschuiven),
   "Importeer oude opzet", "Openen".
3. Uitleg staat bij de knop, niet in een README: de Forms-stappen bij de Forms-knop, de
   scope-uitleg bij de scopebalk.
4. Alle foutmeldingen nalopen: Nederlands, met wat de gebruiker kan doen. Geen tracebacks in
   de UI; die gaan naar een logbestand in `%LOCALAPPDATA%/Lesgeefplanner/log.txt`, met een
   knop "Kopieer technische details" bij de foutmelding.
5. README herschrijven als korte, geïllustreerde handleiding in het Nederlands. De huidige
   YAML-documentatie vervalt volledig.

**Klaar wanneer:** iemand die het project niet kent, komt met alleen de app van niets tot een
geëxporteerd rooster.

---

## Fase 10 — Distributie

**Doel:** overdracht is "download dit bestand".

Taken:
1. PyInstaller-spec: onefile, alle NiceGUI-statics en de ortools-libs meebundelen
   (`--collect-all nicegui --collect-all ortools`). Console verbergen.
2. GitHub Actions workflow: op tag `v*` bouwen op `windows-latest`, artefact aan de Release
   hangen.
3. Testen op een schone Windows-machine: dubbelklik → browser opent → nieuw project → export.
4. Releasepagina met SmartScreen-uitleg ("Meer info → Toch uitvoeren") inclusief screenshot.
5. `src/` (oud) en `ui/` (oud) en `main.py` verwijderen.
6. `docs/ONTWIKKELAAR.md`: hoe je het lokaal draait met uv, hoe je een release maakt.

**Valkuilen:**
- Bundelgrootte: controleer dat `matplotlib`, `scipy` en `ipykernel` er echt uit zijn.
- Poort: nooit hardgecodeerd 8080; als 8080 bezet is start de app anders niet.
- Bestandspaden: de app mag niets schrijven naast de exe (die staat vaak in `Downloads` of
  `Program Files`). Documenten kiest de gebruiker, instellingen gaan naar `%LOCALAPPDATA%`.

**Klaar wanneer:** een schone Windows-machine draait de exe zonder Python, uv of internet.

---

## Fase 11 — Optioneel, na oplevering

* Ervaring opgebouwd tijdens het seizoen meewegen bij `geen_ervaren`: definieer "ervaren" per
  les als `ervaring_jaren >= 1 or lessen_gegeven_dit_seizoen_voor_deze_datum >= K` (K
  instelbaar, standaard 3). De ervarenset wordt dan per les anders; bouw hem in de lus over
  lessen, niet één keer vooraf.
* Datumprikker-import.
* De screeningvraag in het formulier.
* Google Sheets API in plaats van het xlsx-bestand.
* Slepen van lesgevers tussen lessen.
* ICS-export en een overzicht per persoon.

---

## Volgorde-afhankelijkheden

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
              ↘ 6 kan parallel aan 4/5 als de modellen uit fase 1 staan
              ↘ 7 heeft alleen fase 1 + 2 nodig
```
Fase 3 is het eerste punt waarop de app echt bruikbaar is. Fase 8 is het punt waarop de oude
YAML-flow mag verdwijnen. Ga niet naar fase 10 voordat 9 af is; een gepolijste installatie van
een verwarrende app helpt niemand.
