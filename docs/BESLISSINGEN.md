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
