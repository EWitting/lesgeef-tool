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
