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
