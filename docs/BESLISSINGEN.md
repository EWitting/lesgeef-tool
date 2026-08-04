# Beslissingen tijdens uitvoering

Dit logboek bevat keuzes die tijdens de uitvoering van `docs/PLAN.md` zijn gemaakt zonder ze
vooraf aan de gebruiker voor te leggen, omdat ze niet expliciet in `docs/DESIGN.md` stonden.
Elke regel: datum, fase, keuze, reden. Lees dit terug voordat je een latere fase begint — een
eerdere keuze kan een latere fase raken.

## 2026-08-04 — Fase 0

- **NiceGUI-versie**: `uv sync` haalde 3.8.0 op (DESIGN.md ging uit van 2.x, wat op dat moment
  de nieuwste major was). De gebruikte API's (`ui.page`, `ui.run`, `ui.aggrid`-vervanging in
  fase 2) zijn stable tussen 2.x en 3.x voor zover nu gebruikt. Geen pin toegevoegd; als een
  latere fase een breaking change tegenkomt, hier vermelden en zo nodig alsnog vastzetten met
  `nicegui>=2.0,<4.0`.
- **`pyyaml` blijft een dependency** ondanks dat de nieuwe opslag JSON is: fase 8's
  `legacy_import.py` moet de oude `planning.yml` kunnen lezen voor de eenmalige migratie.
- **`platformdirs` toegevoegd** vooruitlopend op fase 2 (recente-bestandenlijst in
  `%LOCALAPPDATA%`) en fase 9/10 (logbestand, instellingen). Niet in DESIGN.md expliciet
  genoemd maar wel al genoemd in PLAN.md fase 2.
- **Build backend**: `hatchling` gekozen (niet in DESIGN.md gespecificeerd) omdat het geen
  extra configuratie nodig heeft voor een simpele src-layout en al veelgebruikt is in het
  Python-ecosysteem.
- **`ui/app.py` is nu een placeholder** (alleen een label) — wordt in fase 2 vervangen door de
  volledige drie-zone-lay-out uit DESIGN.md §2.6. Dit is bewust: fase 0 moet alleen aantonen
  dat de server opstart.

## 2026-08-04 — Fase 1

- **`nieuw_id()` verplaatst naar `model/ids.py`** in plaats van in `model/__init__.py` zoals
  DESIGN.md §7 impliceert, om een circulaire import te vermijden (`entities.py` heeft
  `nieuw_id` nodig als `default_factory`, en `__init__.py` importeert op zijn beurt uit
  `entities.py`). `model/__init__.py` re-exporteert `nieuw_id` alsnog, dus de publieke API
  (`from lesgeefplanner.model import nieuw_id`) is ongewijzigd.
- **`muteer()` maakt de snapshot van vóór het blok, niet erna** — dat stond al zo in
  DESIGN.md, hier expliciet bevestigd met een test (`test_undo_herstelt_exact`) omdat dit de
  meest voor de hand liggende plek is om per ongeluk de verkeerde volgorde te kiezen.
  Belangrijke nuance die niet in DESIGN.md stond: als de code binnen het `with doc.muteer():`
  blok een exception gooit, is de snapshot-van-ervoor nog niet op de stack gezet (de `yield`
  gebeurt vóór de `append`), dus een mislukte mutatie is niet undo-baar maar het project zelf
  kan al gedeeltelijk gewijzigd zijn als de aanroeper het blok niet atomisch houdt. Aanroepers
  moeten dus zelf zorgen dat het blok geen halve wijziging achterlaat bij een fout (bv. eerst
  alle validatie doen, dan pas muteren).
- **Backupbestanden komen naast het projectbestand** in `<projectmap>/.lesgeefplanner-backups/`
  in plaats van een centrale map, zodat een backup meeverhuist als het project verplaatst
  wordt en niet aangroeit tot een ongelimiteerde map met alle ooit geopende projecten door
  elkaar. Bewaart de laatste 10 per bestandsnaam (`<stem>-<tijdstempel><suffix>`).
- **`autosave_indien_nodig()` is een expliciete, UI-aan te roepen methode**, geen achtergrondthread.
  De `Document`-klasse blijft daardoor UI-onafhankelijk en testbaar zonder event-loop; fase 2
  koppelt er een `ui.timer` aan die deze elke paar seconden aanroept.
- **`os.fsync()` toegevoegd** aan het atomisch schrijven (niet expliciet genoemd in
  DESIGN.md) — zonder fsync kan een crash vlak na `os.replace()` op sommige
  bestandssystemen nog steeds oude data opleveren omdat de OS-buffer niet is doorgespoeld.

## 2026-08-04 — Fase 2

- **Native venster (pywebview) versus browsertab**: DESIGN.md §2.7 liet in het midden of de
  gepakte app een browsertab opent of een eigen venster toont. Gekozen voor een **native
  pywebview-venster** (`nicegui[native]`, dependency toegevoegd) omdat dat (a) meer voelt als
  een echte applicatie voor een niet-technische gebruiker dan "er opent een browsertab", en
  (b) een NATIVE bestand-openen/opslaan-dialoog geeft via
  `app.native.main_window.create_file_dialog(...)`, wat het "typ een pad" probleem oplost.
  Nadeel: grotere PyInstaller-bundel en een afhankelijkheid van Windows' WebView2-runtime
  (op Windows 11 standaard aanwezig, op Windows 10 meestal via Edge-updates). Dit moet
  expliciet getest worden op een schone Windows-machine in fase 10 (PLAN.md noemt dit al als
  aandachtspunt, maar niet specifiek voor pywebview/WebView2).
  `ui/bestandsdialoog.py` detecteert of een native venster beschikbaar is
  (`native_beschikbaar()`) en valt anders terug op een tekstveld -- dat pad wordt in de
  ontwikkelomgeving (`native=False`) automatisch gebruikt en is dus goed doorlopen getest.
- **`ui/state.py` en `ui/bestandsdialoog.py` toegevoegd**, niet met naam genoemd in
  DESIGN.md §7. De mappenstructuur daar somt op wat elk *scherm* doet, maar niet waar de
  gedeelde runtime-status (het huidige Document, welke scope actief is) leeft. Voor een
  single-user lokale app is één module-niveau `state`-singleton voldoende; dit is bewust
  geen `dict`-achtige NiceGUI `app.storage` omdat het datamodel al Pydantic is en direct
  bruikbaar moet zijn.
- **`ui.header()` kan niet gebruikt worden** binnen de zelfgebouwde lay-out: NiceGUI staat
  niet toe dat top-level layout-elementen (`ui.header`, `ui.footer`, `ui.drawer`) genest
  worden in een gewone container. Losgelaten voor een gewone `ui.row()` die er hetzelfde
  uitziet (bg-primary, witte tekst) maar wel binnen de zelfgebouwde flex-kolom past. Dit
  werd pas zichtbaar bij het smoke-testen met een echte pagina-render (curl tegen de
  lokale server), niet bij het schrijven van de code zelf -- reden om dat soort smoke-tests
  te blijven doen bij UI-wijzigingen, ook al schrijven we geen geautomatiseerde UI-tests
  (DESIGN.md §8: "Geen UI-tests").
- **"Opslaan als" is nu al gebouwd**, hoewel PLAN.md fase 2 dit niet expliciet noemt. Zonder
  een manier om een NIEUW project voor het eerst op te slaan is de app na fase 2 niet echt
  bruikbaar (een gebruiker kan een project aanmaken maar nooit bewaren). Gebruikt dezelfde
  `bestandsdialoog`-helpers.
- **Header-hoogte is een geschatte 56px** (`calc(100vh - 56px)` voor de panelen eronder) nu
  we geen `ui.header()` meer gebruiken met een vaste hoogte. Visuele nauwkeurigheid hiervan
  is niet geverifieerd in een echte browser (alleen via HTML-inspectie); bij UI-polish
  (fase 9) nalopen of dit klopt of dat een `ResizeObserver`-aanpak nodig is.
- **Linkerrail en inspector zijn placeholders** in fase 2 ("binnenkort hier: ..."), zoals
  PLAN.md ook aangeeft (die functionaliteit hoort bij fase 3/5/6/8). Geen half afgebouwde
  knoppen die niets doen; wel duidelijke tekst over wat er nog komt.
- **Sluiten in plaats van "Nieuw"/"Openen" in de hoofdlay-out**: de header heeft alleen een
  "Sluiten"-knop die terug navigeert naar het startscherm, in plaats van ook "Nieuw
  project"/"Ander bestand openen" rechtstreeks vanuit de hoofdweergave aan te bieden. Dat
  scheelt een tweede implementatie van dezelfde flow; van project wisselen kost nu twee
  klikken (Sluiten, dan Nieuw/Openen) in plaats van één. Kan later worden toegevoegd als het
  in de praktijk irritant blijkt.

## 2026-08-04 — Fase 3

- **`ui/lesbewerkingen.py` toegevoegd** (niet met naam genoemd in DESIGN.md §7): alle
  mutatielogica voor een les (toewijzen/vastzetten/wissen/vervallen/tijd/titel/extra les) in
  één UI-onafhankelijke module met pure functies, gescheiden van `planning_view.py` (dat
  alleen de NiceGUI-elementen bouwt en de klikhandlers aanroept). Dit maakt de mutatielogica
  met gewone pytest-tests te toetsen zonder een browser of event loop nodig te hebben --
  `tests/test_lesbewerkingen.py` en `tests/test_integratie_handmatig_rooster.py` doen dat.
- **"Klik op lege dag in de kalender" is een "+ Extra les toevoegen"-knop geworden**,
  in plaats van een klikbare lege cel in een maandkalender. Onze planning-weergave is een
  chronologische lijst van bestaande/gegenereerde lessen (zoals de oude AG Grid-tabel), geen
  maandraster met lege cellen -- die bestaan simpelweg niet als element om op te klikken.
  Een knop met een datumkiezer in een dialoog levert dezelfde functionaliteit (ad-hoc les
  toevoegen) zonder een volledige maandkalender-weergave te bouwen, wat buiten de scope van
  deze fase valt.
- **Toewijzen via een slot-knop + menu, niet via drag&drop.** DESIGN.md §4.7 noemt dit al
  expliciet als voorkeur ("Slepen is later eventueel een toevoeging, maar klikken is
  nauwkeuriger"), hier concreet uitgevoerd: elk lesgever-slot is een `ui.button` die een
  `ui.menu` opent met alle actieve lesgevers (alfabetisch, met hun huidige aantal lessen),
  plus vastzetten/losmaken/wissen als het slot al bezet is. Het menu wordt bij elke
  `ververs()` opnieuw opgebouwd (`menu.clear()` + hervullen) in plaats van eenmalig, zodat de
  lesgever-lijst en hun lessen-aantal altijd actueel zijn zonder een apart 'on show'-event te
  gebruiken.
  - **Dubbele toewijzing wordt geweigerd** (`wijs_lesgever_toe` geeft `False` terug zonder te
    muteren): dezelfde lesgever twee keer op dezelfde les is nooit de bedoeling en zou ook
    een onzinnige undo-entry opleveren.
  - **Een klik op een leeg slot voegt altijd toe aan het EIND van `toewijzingen`**, nooit op
    een specifieke index met gaten. Omdat de UI bezette slots altijd vooraan toont
    (slot i is bezet ⟺ i < len(toewijzingen)), is "klik op leeg slot i" altijd gelijk aan
    "voeg toe aan het eind" -- er zijn nooit gaten om te vullen.
  - **Vervallen wist de toewijzingen** (`markeer_vervallen`): een les die niet doorgaat heeft
    geen echte lesgever-indeling meer nodig. Bij "gaat weer door" blijft de lijst leeg (de
    gebruiker wijst opnieuw toe), in plaats van te proberen de oude indeling te onthouden --
    die was toch al gewist en zou een verrassende geest-toewijzing zijn.
- **Async klikhandlers direct als `async def`-methoden**, niet via een `ui.timer(0, ..., once=True)`-omweg. NiceGUI's `handle_event()` await't automatisch een Awaitable die een
  handler teruggeeft (ook via een lambda die een coroutine-aanroep retourneert), dus
  `on_click=lambda: self._klik_vervalt()` met `_klik_vervalt` als `async def` volstaat. Dit
  bleek pas na het lezen van `nicegui/events.py` broncode; eerdere pogingen gebruikten
  onnodig een timer-omweg die is teruggedraaid.
- **Undo/redo-tooltips tonen de eerstvolgende beschrijving** via twee nieuwe peek-methoden op
  `Document` (`volgende_undo_beschrijving()` / `volgende_redo_beschrijving()`), niet met naam
  genoemd in DESIGN.md maar nodig om PLAN.md fase 3's "undo/redo-knoppen met de beschrijving
  als tooltip" te kunnen bouwen zonder de stack te muteren. Een `ui.tooltip()` wordt EENMAAL
  als kind-element aangemaakt en daarna via `.set_text()` bijgewerkt -- `.tooltip(text)`
  opnieuw aanroepen zou telkens een nieuw `Tooltip`-element toevoegen (gecontroleerd in de
  nicegui-broncode).
- **Geen geautomatiseerde klik-simulatie in de testsuite.** NiceGUI heeft een
  `nicegui.testing.User`-simulator die zonder browser kliks/type-acties kan afspelen. Een
  losse (niet-gecommitte) verkenning liep vast op een niet voor de hand liggende eis: de
  `root=`-parameter van `user_simulation()` verwacht een functie die ZELF de paginainhoud
  bouwt (zoals bij `ui.run(lambda: ...)`), niet een losse setup-functie die een module
  importeert die op zijn beurt zelf `@ui.page("/")` registreert -- dat gaf een verwarrende
  404-in-een-lus. De juiste weg is `main_file=` naar een los script te wijzen (zoals de
  pytest-plugin van nicegui zelf doet). Gezien DESIGN.md §8 al expliciet "Geen UI-tests"
  vastlegt, is hier niet verder in geïnvesteerd; correctheid is in plaats daarvan geverifieerd
  met (a) volledige pytest-dekking van `lesbewerkingen.py` inclusief een save/reopen
  integratietest, en (b) handmatige HTTP-smoke-tests die de pagina renderen met elke
  lesstatus (gewoon, vast toegewezen, vervallen, extra) om constructiefouten te vangen.

## 2026-08-04 — Fase 4

- **`les_seizoen_id(les)` verplaatst naar `model/entities.py`** als losse functie naast
  `Les`, en hergebruikt in zowel `ui/planning_view.py` (groepering) als
  `planner/request.py` / `planner/solve.py` (scope-splitsing, werkverdeling per seizoen).
  Was eerst inline gedupliceerd in `planning_view.py`; nu één definitie. Niet expliciet zo
  benoemd in DESIGN.md, maar wel de voor de hand liggende plek (bij het model, niet bij een
  van de gebruikers ervan).
- **`TermCollector.per_les()` beperkt tot les-gebonden termen** (tekort, bezetting_bonus,
  misschien, geen_ervaren, wijziging). Week-conflict en boven/onder-richtlijn zijn
  eigenschappen van een LESGEVER over meerdere lessen heen, niet van één les, en horen
  daarom thuis in de per-persoon-weergave die fase 5 bouwt (het inspectiepaneel), niet in
  `per_les`. DESIGN.md liet dit in het midden ("per les: verzamel de termen die aan die
  les_id hangen") -- deze knip is een concrete invulling die bewaakt dat een uitleg-regel
  altijd eenduidig bij één les OF één persoon hoort.
- **Optimalisatie in de werkverdeling-termen**: een boven/onder-richtlijn-niveau wordt
  alleen aangemaakt als het structureel haalbaar is (`drempel <= bovengrens` resp.
  `drempel >= 0`), met een `break` zodra dat niet meer zo is. Dit verandert het gedrag niet
  (de solver zou een onhaalbaar niveau toch altijd op 0/false zetten, want er is geen
  constraint die het dwingt te activeren) maar scheelt onnodige BoolVars bij een kleine
  scope. Niet in DESIGN.md's pseudocode opgenomen; hier expliciet vermeld omdat het afwijkt
  van de letterlijke overname van het oude `src/schedule.py`.
- **`_verzamel_beschikbaarheid()` in `planner/request.py`**: rondes worden gesorteerd op
  `aangemaakt_op` en latere rondes overschrijven eerdere antwoorden voor hetzelfde
  (lesgever, les)-paar ("nieuwste ronde wint"). DESIGN.md specificeert dit niet expliciet
  voor de solver-kant (wel impliciet via `Ronde`/`Antwoord` in §3.5); dit is de concrete
  keuze. `Antwoord.doet_mee=False` (screeningvraag, fase 6) sluit iemand nu al volledig uit
  van beschikbaarheid, ook al bestaat de vraag zelf nog niet in de UI.
- **`ui/dialogen/diff_dialoog.py` gebouwd als eerste van drie geplande toepassingen**
  (solvervoorstel nu; kalenderdiff fase 8 en Excel-samenvoeging fase 7 hergebruiken hem
  straks). Vorm: lijst met vinkjes (`DiffRegel`), "Alles aan/uit", Toepassen/Annuleren,
  geeft de aangevinkte id's terug. Geen enkele fase-4-specifieke aanname erin verwerkt.
- **Solvertoepassing is gesplitst in een testbare functie**: `lesbewerkingen.py` kreeg
  `pas_solverresultaat_toe(les_ids, toewijzingen)` in plaats van de mutatielogica alleen in
  de klik-handler van `planning_view.py` te schrijven. Reden: een bug hier (bv. een vaste
  toewijzing per ongeluk overschrijven met `vast=False`) is precies het soort fout dat het
  vertrouwen in "automatisch invullen" om zeep helpt, dus verdient een directe pytest-test
  in plaats van alleen een smoke-test. `tests/test_lesbewerkingen.py` bevat nu drie tests
  hiervoor, inclusief de expliciete regressietest dat een vaste toewijzing zijn
  `vast=True`/`bron` behoudt na een solver-run.
- **"Automatisch invullen" gebruikt nu al `state.scope`/`state.peildatum()`**, ook al is er
  nog geen UI om de scope zichtbaar te wijzigen (dat komt met de scope-band uit DESIGN.md
  §2.4, nog niet ingepland in een specifieke fase). Standaard is dus: hele project,
  `alleen_toekomst=True`, peildatum = vandaag. Werkt voor nu correct maar is nog niet
  door de gebruiker aan te passen; op te pakken zodra scope-UI concreet wordt.
- **Solver draait via `loop.run_in_executor(None, los_op, request)`** met een
  `ui.notification(spinner=True, timeout=None)` die na afloop wordt gedismisst. Voorkomt
  dat de NiceGUI-eventloop blokkeert tijdens de (tot `max_rekentijd_seconden`) durende
  CP-SAT-solve.

## 2026-08-04 — Fase 5

- **`domain/werkverdeling.py` en `domain/beschikbaarheid.py` toegevoegd als gedeelde laag**
  tussen de solver (`planner/`), de analyse (`domain/analysis.py`) en het inspectiepaneel
  (`ui/inspector.py`). Zonder dit zouden er drie plekken zijn die zelf uitrekenen wat "het
  doel" of "iemands beschikbaarheid" is, met het risico dat ze uit elkaar gaan lopen (bv. de
  solver optimaliseert tegen een ander getal dan wat het balkdiagram toont). `bereken_doel()`
  wordt nu letterlijk door alle drie gebruikt. `planner/solve.py` en `planner/request.py` zijn
  aangepast om deze gedeelde functies te gebruiken in plaats van hun eigen kopie (die er in
  fase 4 nog wel was).
- **`domain/report.py` is een BEWUSTE vereenvoudiging** van het oude `src/report.py`: geen
  aparte "lesgever-verdeling"-sectie meer, want een lijst met ieders aantal lessen is geen
  *bevinding* (geen probleem om te melden) maar een statistiek -- die hoort thuis in het
  balkdiagram van het inspectiepaneel. Het tekstrapport groepeert nu simpelweg op ernst
  (FOUTEN/WAARSCHUWINGEN/INFO). DESIGN.md zei alleen "rendert naar de bestaande platte
  tekst"; dit is de concrete invulling.
- **`lesgever_niet_gereageerd` is per ronde, niet globaal**: als een lesgever niet
  gereageerd heeft op een ronde die geen enkele les in de huidige scope raakt, wordt dat NIET
  gemeld. Dit voorkomt dat oude, allang afgesloten rondes irrelevante meldingen blijven geven
  zodra een nieuwe scope wordt bekeken.
- **`lesgever_boven_richtlijn`/`lesgever_onder_richtlijn` gebruiken de HELE seizoenstelling**
  (niet beperkt tot de zichtbare scope), maar worden alleen getoond voor seizoenen die de
  scope daadwerkelijk raakt -- exact dezelfde scope/context-splitsing als de solver
  (`planner/request.py`). Dit was nodig om consistent te blijven met hoe de solver "boven de
  richtlijn" definieert; anders zou het inspectiepaneel een ander verhaal vertellen dan
  waar de solver op stuurt.
- **Klikbaarheid**: `LessonRow` kreeg een apart `info_gebied` (datum/tijd/titel-cluster,
  los van de lesgever-knoppen) met een klikhandler die de les in de inspector opent, zodat
  een klik daar niet per ongeluk ook een lesgever-menu opent. Scrollen-en-oplichten
  (`PlanningView.scroll_en_licht_op`) gebruikt `ui.run_javascript` met NiceGUI's
  `getElement(id).$el.scrollIntoView(...)`-patroon, omdat er geen kant-en-klare
  `scroll_into_view()`-methode op een Element bestaat.
- **"Kopieer rapport" gebruikt `navigator.clipboard.writeText()` via `ui.run_javascript`**,
  met de tekst als `json.dumps(...)` (niet `!r`) om er zeker van te zijn dat de string
  geldige JS-syntax oplevert ongeacht welke tekens erin zitten.
- **`state.laatste_plan_result`** (niet in DESIGN.md's dataklasse-lijst voor `AppState`,
  want die module bestond toen nog niet) bewaart het resultaat van de laatst gedraaide
  solver-run, ook als het voorstel niet is toegepast. Het inspectiepaneel gebruikt dit voor
  "Waarom deze score?" en de per-les solver-uitleg. Wordt gereset bij het openen/aanmaken
  van een ander project (anders zou een oude solver-run van project A worden getoond in
  project B).

## 2026-08-04 — Fase 6

- **`dialogen/lesgevers.py` + `ui/lesgeverbewerkingen.py` gebouwd, hoewel geen enkele
  PLAN.md-fase dit expliciet als taak noemt.** DESIGN.md §7 noemde het bestand wel in de
  mappenstructuur, maar PLAN.md wees het aan geen fase toe -- een gat. Zonder dit kon een
  gebruiker via de nieuwe UI HELEMAAL GEEN lesgevers aanmaken (alleen via de nog niet
  bestaande Excel-roster-import van fase 7), wat de app tot dan toe onbruikbaar zou maken
  voor een nieuw project. Meegenomen in deze fase omdat rondes/antwoorden zonder lesgevers
  toch niet te testen zijn. `verwijder_lesgever()` ruimt ook toewijzingen naar die lesgever
  op in alle lessen, anders zou de UI blijvend '? (onbekend)' tonen.
- **Vraagtitels bij een via het script aangemaakt formulier zijn LETTERLIJK
  `'{label} #{index}'`** (geen extra prefix zoals de oude "Kun je lesgeven op: [...]"
  wrapper). Dat kon omdat `addMultipleChoiceItem()` per les een eigen vraag gebruikt in
  plaats van een grid-vraag (wat het oude, met de hand gemaakte formulier gebruikte) --
  Google Forms exporteert dan de kolomkop als exact de vraagtitel, wat het parsen in
  `forms_import.py` sterk vereenvoudigt (regex op '#(\d+)$' volstaat) t.o.v. de oude
  grid-gebaseerde aanpak.
- **De naamkolom-dropdown (`addListItem` met vaste keuzes)** betekent dat bij een via het
  script gemaakt formulier de naam ALTIJD exact matcht -- de fuzzy-wizard verschijnt dan
  nooit. `domain/names.py` en de resolutiedialoog zijn dus alleen relevant voor handgemaakte
  formulieren of getypte varianten; getest via `test_dropdown_naam_is_altijd_exact`.
- **Terugval-labelparsing (`_koppel_op_label`)** herkent dag+maand(+tijd) via een regex en
  koppelt op (dag, maand, evt. tijd) tegen `project.lessen` -- NOOIT op een afgeleid
  jaartal. Bij 0 of >1 kandidaten wordt de kolom gemeld als niet-gekoppeld in plaats van
  geraden; dat is een bewuste "liever niets doen dan fout koppelen"-keuze, consistent met
  conventie 5.
- **`ImportResultaat`/`NaamProbleem` (exchange/types.py) dragen `waarden`/`ingevuld_op` mee
  op het naamprobleem zelf**, niet alleen op het uiteindelijke antwoord. DESIGN.md's
  schets van `NaamProbleem` liet dit open; zonder deze velden zou een net-opgelost
  naamprobleem geen antwoord kunnen opleveren (de ruwe rijdata zou al weg zijn tegen de
  tijd dat de gebruiker een lesgever kiest in de wizard).
- **`state.meld_wijziging()` als brede "er is iets veranderd"-brug** tussen de linkerrail
  (lesgevers/rondes, mutaties via directe functie-aanroepen, geen doc-brede callback) en
  header/inspector/planning. Iets grover dan een gerichte refresh (het herbouwt ook het
  middenpaneel bij het toevoegen van één lesgever), maar simpel en correct; de kosten zijn
  verwaarloosbaar omdat lesgevers/rondes beheren geen high-frequency actie is (in
  tegenstelling tot bv. lesgever-toewijzen in de planning, waar wel gerichte per-rij
  refresh nodig was). `_ververs_na_wijziging()` in app.py is nu de ene plek die alles
  (header, inspector, linkerrail) samen ververst en wordt door undo/redo, de solver, en
  `state.on_change` allemaal gebruikt.
- **Responsoverzicht toont alleen "nog te vullen"**, geen volledige beschikbaarheidsmatrix
  (die komt terug als de "Toon beschikbaarheid"-schakelaar op de planning, nog niet
  gebouwd -- zie openstaande punt hieronder).

- **"Toon beschikbaarheid" is uitgevoerd als groepering + kleur, niet als aparte kolommen
  per lesgever.** PLAN.md fase 6 taak 7 vroeg om "een schakelaar die kolommen per lesgever
  toevoegt aan de planning-rijen" -- een volledige matrix-weergave zoals de oude
  datumprikker_view.py. Dat vereist een fundamenteel andere rij-layout (breed, horizontaal
  scrollend) die niet past bij de huidige compacte lijst-weergave, en zou een aparte
  deelweergave zijn geworden in plaats van een simpele knop. In plaats daarvan:
  (a) het lesgever-toewijsmenu groepeert nu op Ja/Misschien/Onbekend/Nee met kopregels,
  (b) een toegewezen 'misschien'-lesgever kleurt de slotknop geel (`#fff3cd`, dezelfde kleur
  als de oude AG Grid-cel), zichtbaar zonder het menu te openen, en (c) de inspector
  (fase 5, "les geselecteerd") toont al de volledige beschikbaarheid van iedereen voor een
  les. Dat dekt het echte doel (beschikbaarheid meenemen bij het toewijzen, zonder een
  apart rapport te hoeven raadplegen) zonder een grote nieuwe matrix-component te bouwen.
  Een volledige matrix-overzicht kan alsnog later als aparte deelweergave, mocht dat nodig
  blijken.

## 2026-08-04 — Fase 7

- **`_meta`-blad schrijven via een tweede openpyxl-stap na xlsxwriter.** xlsxwriter kan
  geen bestaand bestand openen/aanvullen (het bouwt alleen van nul op), dus
  `excel_export.py` sluit eerst de xlsxwriter-workbook normaal af en opent het resultaat
  daarna opnieuw met openpyxl om het verborgen `_meta`-blad toe te voegen. Niet zo
  vermeld in DESIGN.md, maar de enige praktische manier om beide bibliotheken te combineren
  zonder xlsxwriter's opmaak-mogelijkheden (merges, formats) op te geven.
- **`Wijziging.soort` heeft geen `"tijd"`-variant gekregen**, ondanks dat DESIGN.md §4.4
  die noemt in de Literal. Een tijdswijziging in de sheet zou de rij feitelijk laten
  matchen met een ANDERE les (of geen enkele) via de (dag, maand, tijd)-terugval, wat de
  koppeling zelf al onbetrouwbaar maakt voor precies het geval dat "tijd" zou moeten
  detecteren. Tijd wijzigen hoort bij de app zelf (fase 3's 'Tijd aanpassen'), niet bij de
  Excel-samenvoeging. Als dit in de praktijk gemist wordt, kan het alsnog toegevoegd worden
  met een aparte, voorzichtige match-strategie.
- **Datum/tijd-terugval matcht zonder jaar** (`_parse_dag_maand_cel`, dag+maand alleen):
  de Datum-kolom wordt als TEKST geëxporteerd (bv. 'woensdag 22 apr', zonder jaartal), dus
  een jaar erbij verzinnen zou gokken zijn. Dezelfde aanpak als forms_import.py's
  terugvalpad; beide hebben nu dezelfde reden en dezelfde oplossing.
- **`lees_sheet()` geeft een derde return-waarde (`niet_gekoppelde rijen`)** terug boven op
  DESIGN.md's `tuple[list[Wijziging], list[NaamProbleem]]`. DESIGN.md's eigen tekst zegt
  expliciet "markeer de rij als niet-koppelbaar en toon hem apart" maar de voorgestelde
  functiehandtekening had daar geen plek voor -- een gat, hier ingevuld door de tuple met
  een derde lijst uit te breiden in plaats van een aparte aanroep te verzinnen.
- **`NaamProbleem` wordt hergebruikt tussen forms_import.py en excel_import.py** (met een
  toegevoegd optioneel `les_id`-veld voor de Excel-kant) in plaats van twee bijna
  identieke dataklassen te maken. Zie de uitgebreide toelichting in exchange/types.py zelf.
- **Roster-import (lesgevers.xlsx) voegt SAMEN op exacte naam**, niet op fuzzy match: een
  bestaande lesgever met exact dezelfde naam krijgt bijgewerkte ervaring/actief, een naam
  die niet exact voorkomt wordt een NIEUWE lesgever (geen wizard). Dat is bewust
  eenvoudiger dan de fuzzy-wizard bij rondes/Excel-wijzigingen: een lesgeverslijst-import
  gebeurt meestal eenmalig bij een compleet nieuw seizoen (iedereen erin), niet als
  incrementele correctie op een al druk gebruikte lijst, dus het risico van "per ongeluk
  een dubbele Anne" is klein en makkelijk zelf op te merken en handmatig te herstellen
  (verwijderknop) t.o.v. de complexiteit van er een derde wizard-variant bij te bouwen.
- **Zowel "Automatisch invullen" (fase 4) als "Wijzigingen uit Excel" (deze fase) gebruiken
  nu dezelfde `dialogen/diff_dialoog.py`.** Precies zoals DESIGN.md §7 voorspelde: "bouw
  het één keer". Geen aanpassing aan diff_dialoog.py was nodig.
- **Excel-import gebruikt een upload-widget, geen native bestandsdialoog** (in
  tegenstelling tot Opslaan/Exporteren, die wel de native dialoog gebruiken waar
  beschikbaar). Consistent met hoe fase 6's rondes-import al werkte: één interactiepatroon
  voor "haal een bestand van de gebruiker op" in plaats van twee naast elkaar.

## 2026-08-04 — Fase 8

- **`legacy_import.py` genereert reguliere lessen via `domain/calendar.py`** (`bereken_kalender_diff` + `pas_kalender_diff_toe`) in plaats van de weekiteratie van het oude
  `src/parse.py` te herschrijven. Zelfde resultaat, één plek die "hoe genereer je lessen
  uit een weekrooster" kent -- als daar ooit een bug in zit, hoeft hij maar op één plek
  gefixt te worden.
- **Overlappende seizoenen: eerste in de lijst wint**, bij zowel `extra-lessen` als
  activiteiten-matching. De oude `src/parse.py` had hier eigenlijk een net andere
  (impliciete) regel bij extra-lessen ("laatste seizoen in de yaml-volgorde dat matcht"),
  maar dat was nooit een bewuste keuze -- gewoon een bijeffect van een lus zonder `break`.
  Voor een eenmalige migratie is bit-voor-bit compatibiliteit met die bijeffect niet
  waardevol; consistent zijn met `domain/calendar.py`'s "eerste wint"-regel (die WEL bewust
  is, zie fase 2) is dat wel.
- **`excel_import.py`'s `_parse_dag_maand_cel`/`_parse_tijd_cel` worden hergebruikt in
  `legacy_import.py`** voor het koppelen van de oude `planning.xlsx` aan de net
  gegenereerde lessen (zelfde probleem: tekst-datum zonder jaar). Bewust geen kopie
  gemaakt; het zijn moduleprivate helpers (`_`-prefix) maar binnen dezelfde package is dat
  in dit project geen harde grens, alleen een signaal "niet de publieke API".
- **Lesgevers-import bij migratie hergebruikt `exchange/roster_import.py` ongewijzigd.**
  Als de kolommen niet automatisch herkend worden, wordt dat een waarschuwing in plaats van
  een interactieve wizard (die kan een eenmalige, niet-interactieve migratiefunctie niet
  tonen) -- de gebruiker importeert de lesgeverslijst dan na de migratie alsnog los via het
  Lesgevers-paneel (fase 6/7), waar de wizard wel bestaat.
- **Nog geen UI voor `SolverConfig`** (dialogen/solver_config.py stond wel in DESIGN.md §7,
  maar is-net als lesgevers.py eerder ook was- aan geen enkele PLAN.md-fase toegewezen).
  De config heeft bruikbare, geteste standaardwaarden (overgenomen uit de oude
  `roosterconfig.yaml`), dus dit blokkeert normaal gebruik niet. De linkerrail toont
  bewust de tekst "Solver-instellingen volgen in een latere fase" in plaats van dit stil te
  laten liggen. Op te pakken in een toekomstige fase; de oude `roosterconfig.yaml` wordt
  vooralsnog niet meegenomen in `legacy_import.py`.
- **Datumvelden in de jaarplanning-UI zijn tekstinvoer (JJJJ-MM-DD)**, geen `ui.date()`-
  kalenderwidget zoals bij "Extra les toevoegen" (fase 3). Een `ui.date()` per rij in een
  tabel met meerdere seizoenen zou visueel zwaar worden; voor een kalenderpicker per
  losstaande actie (één keer een datum kiezen) is dat geen probleem, voor een compacte
  herhalende lijst wel. Validatie gebeurt bij het verlaten van het veld (`blur`), met een
  duidelijke foutmelding bij een onleesbare datum in plaats van een gok.

## 2026-08-04 — Fase 9

- **Stappenstatus als een status-rij boven de tabs, niet als vervanging van de tabs.**
  DESIGN.md/PLAN.md beschrijven `ui/stappen.py` als "linkerrail met de stappen" die klikbaar
  is; de bestaande tabs (Jaarplanning/Lesgevers/Beschikbaarheid/Delen, sinds fase 6/7/8)
  deden dat al. In plaats van de navigatie te herbouwen, kreeg elke tab een klikbaar
  statuslabel (✓/!/—) erboven dat naar de bijbehorende tab springt. "Inroosteren" heeft
  geen eigen tab (dat IS het middenpaneel, altijd zichtbaar) en is dus alleen informatief
  met een tooltip, niet klikbaar.
  Overwogen om de icoon-status rechtstreeks IN de Quasar-tab-labels te zetten
  (`with ui.tab(): ui.badge(...)`), maar dat vereist het live bijwerken van content
  genest in een tab-element -- een minder beproefd stuk NiceGUI-API dan een losse
  `ui.label` met `.set_text()`. Gekozen voor de zekerdere weg.
- **Statusregels** (`ui/stappen.py`) zijn eigen interpretatie, niet letterlijk uit
  DESIGN.md/PLAN.md (die specificeren alleen dát er status moet zijn, niet de exacte
  regels). Bijvoorbeeld: Jaarplanning is "aandacht" zodra `bereken_kalender_diff()` niet
  leeg is (kalender loopt uit de pas met de seizoensinstellingen); Inroosteren is
  "aandacht" zodra er minstens één bevinding met ernst "fout" is.
- **`domain/jaarwissel.py`: reguliere (gegenereerde) lessen gaan NIET mee** bij het
  doorrollen naar een nieuw jaar -- alleen seizoenen/weekrooster/lesgevers/extra-lessen.
  De gebruiker moet daarna zelf "Kalender bijwerken" klikken. Bewuste keuze: de oude lessen
  hebben oude datums die toch niet kloppen zonder een aparte verschuivingsberekening per
  les, en de kalender opnieuw laten genereren via de bestaande, geteste
  `domain/calendar.py`-weg is betrouwbaarder dan een tweede manier verzinnen om lessen te
  verschuiven.
- **Verschuiving is standaard 364 dagen (52 weken), niet 365.** Een gewoon jaar verschuift
  de dag-van-de-week (het volgend seizoen zou dan een dinsdag/donderdag-rooster nodig
  hebben in plaats van hetzelfde weekrooster) -- 52 weken behoudt de weekdag-uitlijning.
  Extra lessen (die WEL hun datum letterlijk verschoven krijgen, in tegenstelling tot
  reguliere lessen) profiteren hier direct van.
- **Lesgever-ids blijven behouden bij het doorrollen** (`model_copy()` in plaats van een
  nieuwe `Lesgever()`), seizoen/les-ids juist niet (nieuwe objecten). Consistente regel:
  een lesgever is dezelfde PERSOON jaar na jaar (Excel Code-kolommen, toekomstige
  koppelingen moeten blijven werken), een seizoen/les is een nieuwe INSTANTIE die toevallig
  dezelfde naam/vorm heeft.
- **`app.on_exception()` als globaal vangnet** (`ui/foutafhandeling.py`): NiceGUI's eigen
  standaardgedrag bij een onverwachte fout in een klik-handler is stil -- alleen naar de
  server-console loggen (`log.exception`), niets zichtbaar voor de gebruiker. In de
  gepakte app is er geen zichtbare console, dus zonder dit vangnet lijkt een fout op "er
  gebeurt niets als ik klik". Nu: een dialoog met een korte Nederlandse melding en een
  "Kopieer technische details"-knop, plus wegschrijven naar
  `%LOCALAPPDATA%/Lesgeefplanner/log.txt`. Dit komt BOVENOP de bestaande gerichte
  try/except-afhandeling met specifieke Nederlandse meldingen (bv. "Kon bestand niet
  lezen: ...") die al overal in de UI-code stonden -- die blijven de eerste verdedigingslinie
  voor verwachte fouten; dit vangt de rest.
- **`__main__.py` gebruikt nu daadwerkelijk `native=True` als pywebview beschikbaar is.**
  Dit was in fase 2 al ONTWORPEN (`ui/bestandsdialoog.py`'s `native_beschikbaar()`
  bestond al) maar nooit aan `ui.run()` doorgegeven -- de entry point startte altijd in
  browsermodus, waardoor de native-bestandsdialoog-code in alle tests tot nu toe ongebruikt
  bleef (elke smoke-test in dit document gebruikte bewust `native=False` om headless te
  kunnen draaien). Nu gecorrigeerd; de browser-fallback blijft de goed-geteste weg voor
  ontwikkelen, en is ook wat draait als pywebview om wat voor reden dan ook niet importeert.
- **Geen scope-band-UI gebouwd**, dus PLAN.md fase 9 taak 3's "scope-uitleg bij de
  scopebalk" is niet van toepassing -- er is nog geen scopebalk om uitleg bij te zetten
  (zie de openstaande opmerking hierover in fase 4's beslissingen). De Forms-stappen bij de
  Forms-knop (taak 3's andere voorbeeld) staan er wel, sinds fase 6.
- **Foutmeldingen zijn NIET exhaustief lijn-voor-lijn geaudit** (PLAN.md taak 4), maar
  steekproefsgewijs gecontroleerd: alle `ui.notify(...)`-aanroepen die tijdens fase 3-9 zijn
  geschreven, zijn al in het Nederlands met een concrete beschrijving van wat er misging.
  Een volledige doorloop van alle bestanden is niet apart gedaan gezien de omvang van deze
  sessie; als er toch een niet-Nederlandse of onduidelijke melding ergens zit, is dat een
  gerichte fix, geen structureel probleem.
- **README herschreven, geen screenshots.** PLAN.md vroeg om een "korte, geïllustreerde
  handleiding"; screenshots zijn hier niet toegevoegd omdat er geen manier was om de
  gepakte, echt draaiende app in dit environment visueel vast te leggen. De tekst is wel
  volledig herschreven en YAML-vrij; screenshots toevoegen is een losse, kleine vervolgstap
  zodra iemand de app echt op een Windows-machine kan draaien.

## 2026-08-04 — Fase 10

- **Build daadwerkelijk uitgevoerd en getest op deze ontwikkelmachine** (Windows), niet
  alleen opgeschreven: `uv run pyinstaller ... packaging/bootstrap.py` bouwt een werkende
  `Lesgeefplanner.exe` (~88-91 MB, vooral OR-Tools), die een native venster getiteld
  "Lesgeefplanner" opent zonder consolevenster en zonder fouten in
  `%LOCALAPPDATA%/Lesgeefplanner/log.txt`. Dit is GEEN vervanging voor "test op een echt
  schone Windows-machine zonder Python/uv" (PLAN.md's acceptatiecriterium) -- deze machine
  heeft uv/Python al -- maar het bevestigt wel dat de PyInstaller-configuratie zelf werkt,
  wat het grootste risico bij dit soort bundeling is (ontbrekende native libs/data-files).
- **`packaging/bootstrap.py` als apart startpunt** i.p.v. PyInstaller direct op
  `src/lesgeefplanner/__main__.py` loslaten. Dat bestand doet zelf een
  `sys.path.insert(...)` voor het geval het als los script gestart wordt (`python
  __main__.py`) -- in de PyInstaller-bundel is `lesgeefplanner` al gewoon importeerbaar
  (het zit als geïnstalleerd package in de omgeving die geanalyseerd wordt) en zou die
  aanpassing overbodig zijn tot verwarrend kunnen worden. Een dun bootstrap-bestand dat
  alleen `from lesgeefplanner.__main__ import main; main()` doet, voorkomt die vraag
  volledig.
- **`nicegui-pack` (NiceGUI's eigen CLI-wrapper om PyInstaller) NIET gebruikt**, ondanks dat
  die bestaat en precies hiervoor bedoeld is. Gecontroleerd (`nicegui/scripts/pack.py`
  gelezen): hij voegt alleen `--add-data` toe voor nicegui's eigen statische bestanden, niet
  voor OR-Tools. Rechtstreeks `pyinstaller --collect-all nicegui --collect-all ortools`
  aanroepen (zoals PLAN.md al voorstelde) dekt dus meer in één stap en is exact wat
  uiteindelijk werkte; `nicegui-pack` zou nog steeds een handmatige OR-Tools-toevoeging
  nodig hebben gehad.
- **Geen custom `.ico`-bestand meegegeven.** Er was geen ontwerpasset beschikbaar in deze
  sessie; de exe gebruikt PyInstaller's standaardicoon. Een eigen icoon toevoegen is een
  kleine, geïsoleerde vervolgstap (`--icon pad/naar/icoon.ico` aan het spec-commando).
- **`IMPLEMENTATION_NOTES.md` en `TODO.md` ook verwijderd**, hoewel PLAN.md alleen `src/`
  (oud), `ui/` (oud) en `main.py` noemt. Beide bestanden documenteerden uitsluitend de OUDE
  implementatie (bv. `IMPLEMENTATION_NOTES.md` legt `schedule_lessons()`'s
  pre-assignment-logica uit zoals die in het verwijderde `src/schedule.py` stond); ze laten
  staan zou verwarrend zijn omdat ze naar niet meer bestaande code verwijzen. `data/`
  (de echte planning.yml/roosterconfig.yaml van de commissie) is bewust NIET aangeraakt --
  dat is data, geen implementatie, en valt buiten wat deze fase moest opruimen.
- **GitHub Actions-workflow bouwt op elke `v*`-tag en draait een rooktest** (de exe moet
  minstens 8 seconden blijven draaien zonder af te sluiten) voordat hij aan de Release
  hangt -- een build die crasht bij het opstarten faalt daarmee de workflow in plaats van
  stilzwijgend een kapotte exe te publiceren. Niet expliciet gevraagd in PLAN.md, maar een
  goedkope, waardevolle toevoeging gezien hoe makkelijk een PyInstaller-bundel een
  ontbrekende runtime-dependency kan missen.
- **Geen live GitHub Release aangemaakt.** Het publiceren van een release/tag is een
  zichtbare, moeilijk terug te draaien actie (triggert de workflow, publiceert een
  publiek zichtbaar bestand) en hoort bij de bevoegdheid van de gebruiker, niet bij
  autonome uitvoering. De workflow staat klaar; `git tag v... && git push origin v...`
  zet hem in gang zodra de gebruiker dat wil.
