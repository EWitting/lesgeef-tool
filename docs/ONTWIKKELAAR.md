# Voor ontwikkelaars

## Lokaal draaien

Dit project gebruikt [uv](https://docs.astral.sh/uv/).

```sh
uv sync              # installeert alle dependencies (incl. dev-groep)
uv run lesgeefplanner  # start de app (browser als pywebview niet geïnstalleerd is,
                        # anders een native venster)
uv run pytest         # draait de testsuite
```

De broncode staat in `src/lesgeefplanner/`:

- `model/` -- het datamodel (Pydantic), wat er in een `.lesplan`-bestand staat.
- `store/` -- opslaan/laden/undo (`Document`), instellingen, migraties.
- `domain/` -- kalender genereren, analyse/bevindingen, naam-matching, jaarwissel-logica.
  UI-onafhankelijk, puur en goed te testen.
- `planner/` -- de CP-SAT-solver (OR-Tools).
- `exchange/` -- import/export: Excel, Google Forms, de oude YAML-opzet.
- `ui/` -- de NiceGUI-app. `ui/*bewerkingen.py`-bestanden bevatten de mutatielogica per
  onderdeel (los van de weergave), zodat die ook zonder browser te testen zijn.

Het ontwerpdocument, het uitvoeringsplan en het beslissingenlogboek van de rewrite bestaan
lokaal (`docs/DESIGN.md`, `docs/PLAN.md`, `docs/BESLISSINGEN.md`) maar zijn bewust niet in
git getrackt (zie `.gitignore`) -- het zijn interne proces-/planningsnotities van de bouw,
geen doorlopende projectdocumentatie. Vraag de vorige onderhouder erom als je ze nodig hebt.

## Een release maken

De GitHub Actions-workflow (`.github/workflows/release.yml`) bouwt automatisch een
`Lesgeefplanner.exe` en zet die op een GitHub Release zodra er een tag als `v1.0.0` wordt
gepusht:

```sh
git tag v1.0.0
git push origin v1.0.0
```

De workflow start dan de exe kort op als rooktest (moet minstens 8 seconden blijven
draaien zonder te crashen) voordat hij aan de release wordt gehangen.

## Zelf bouwen (Windows)

```sh
uv sync --group dev   # haalt ook pyinstaller binnen
uv run pyinstaller --noconfirm --clean packaging/Lesgeefplanner.spec \
    --distpath packaging/dist --workpath packaging/build
```

Het resultaat staat in `packaging/dist/Lesgeefplanner.exe` (eenmalig, ~90 MB door OR-Tools).
`packaging/bootstrap.py` is het startpunt (los van `src/lesgeefplanner/__main__.py`, dat
zijn eigen `sys.path`-aanpassing doet voor het geval het als los bestand gestart wordt).

**Als dependencies wijzigen**, regenereer je `packaging/Lesgeefplanner.spec` opnieuw in
plaats van hem met de hand aan te passen:

```sh
uv run pyinstaller --noconfirm --clean --name Lesgeefplanner --onefile --windowed \
    --collect-all nicegui --collect-all ortools \
    --distpath packaging/dist --workpath packaging/build --specpath packaging \
    packaging/bootstrap.py
```

Gecontroleerd (handmatig, op deze ontwikkelmachine): de exe bouwt, start een native venster
getiteld "Lesgeefplanner" zonder consolevenster, en sluit zonder fouten in
`%LOCALAPPDATA%/Lesgeefplanner/log.txt` af. Dit is GEEN vervanging voor het testen op een
werkelijk schone Windows-machine zonder Python/uv (docs/PLAN.md fase 10's
acceptatiecriterium) -- dat moet nog los geverifieerd worden, bij voorkeur via de
GitHub Actions-rooktest of handmatig op een andere machine.

### Bekende aandachtspunten

- **Bundelgrootte** (~90 MB) komt vrijwel volledig door OR-Tools; dat is inherent aan de
  solver en niet te vermijden zonder een andere solver-bibliotheek.
- **WebView2**: het native venster gebruikt Windows' ingebouwde WebView2-runtime. Die zit
  standaard in Windows 11 en de meeste geüpdatete Windows 10-installaties (via Edge). Een
  zeer verouderde Windows 10-installatie zonder Edge-updates mist hem mogelijk -- dan valt
  de app terug op browsermodus (zie `src/lesgeefplanner/__main__.py`).
- **SmartScreen**: de exe is niet digitaal ondertekend (een certificaat kost geld en is
  voor een vrijwilligersproject niet in verhouding). Gebruikers moeten "Meer info" →
  "Toch uitvoeren" kiezen bij de eerste keer -- staat al in de releasetekst.
