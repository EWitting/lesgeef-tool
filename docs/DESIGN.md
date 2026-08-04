# Lesgeefplanner — Ontwerp (rewrite)

Dit document beschrijft **wat** we bouwen en **waarom**. `docs/PLAN.md` beschrijft **in welke
volgorde** en met welke acceptatiecriteria. Lees dit document volledig voordat je aan een fase
uit PLAN.md begint.

Status: ontwerp vastgesteld. Branch: `rewrite` (afgetakt van `origin/ui`).

---

## 0. Conventies voor wie dit uitvoert

Deze regels gelden voor alle code in dit project. Wijk er niet van af.

1. **Taal.** Code-identifiers (functies, variabelen, modules) in het Engels. **Uitzondering:**
   domeinbegrippen behouden hun Nederlandse naam omdat ze geen goede vertaling hebben:
   `Les`, `Lesgever`, `Seizoen`, `Beschikbaarheid`, `Toewijzing`, `Weekrooster`, `Scope`.
   Alle tekst die de gebruiker ziet is **Nederlands**.
2. **Geen globale side effects bij import.** Nooit `locale.setlocale()` op module-niveau (of
   überhaupt). Nooit paden relatief aan de working directory. De huidige `src/export.py` doet
   dit wel; dat is precies wat we weghalen.
3. **Geen impliciete betekenis in strings.** "Deze les vervalt" is een veld, geen cel met de
   tekst `"Geen les"`. "Deze toewijzing staat vast" is een veld, geen afgeleide van "de lijst is
   niet leeg".
4. **Namen zijn nooit een join-key.** Alles koppelt op `id`. Namen zijn uitsluitend voor
   weergave en voor *voorstellen* bij import.
5. **Fuzzy matching beslist nooit zelf.** Het levert een gerangschikte suggestielijst op die een
   mens bevestigt. (De huidige code accepteert Levenshtein < 3 stilzwijgend; daardoor wordt
   "Jan" vrolijk aan "Jen" gekoppeld.)
6. **Elke destructieve actie is omkeerbaar.** Undo-stack + bevestigingsdialoog met diff.
7. **Pydantic v2** voor alle modellen. `model_config = ConfigDict(extra="forbid")` op alles wat
   uit een bestand komt.
8. **Typehints overal.** Publieke functies hebben een docstring in het Nederlands met wat er
   in en uit gaat.

---

## 1. Wat er mis is met de huidige opzet

Kort, zodat de reden achter elke ontwerpkeuze duidelijk is.

| Probleem | Waar | Gevolg |
|---|---|---|
| Vier bronnen van waarheid (`planning.yml`, `lesgevers.xlsx`, forms-export, `planning.xlsx`) | `ui/state.py` | Niets overleeft een herstart; beschikbaarheid wordt nooit opgeslagen |
| Excel-round-trip is lossy | `src/importer.py:import_planning` | `Seizoen(begin=datum, eind=datum)` per rij; `ervaring_jaren=0` voor iedereen |
| Betekenis afgeleid uit strings | `"Geen les"` in een lesgeverkolom | Kan niet onderscheiden van een lesgever die zo heet |
| Vastzetten = "heeft lesgevers" | `src/schedule.py` `pre_assigned` | Elke handmatige edit wordt een harde constraint; enige uitweg is "Reset + Auto-fill", die alles wist |
| Activiteiten falen stil | `src/parse.py` | In de huidige `planning.yml` doen Lustrum Trip (16/17 mei) en Vooka (30/31 mei) niets, want Voorseizoen 2 staat uit-gecommentarieerd. Geen waarschuwing. |
| Verleden telt niet mee in werkverdeling | `src/schedule.py` `skip_les_indices` | Wie al 5 lessen gaf lijkt even onbelast als wie er 0 gaf — precies verkeerd bij herplannen |
| Jaar geraden uit response-timestamp | `src/importer.py:import_forms_datumprikker` | Fout zodra een seizoen over de jaarwisseling loopt (sep→apr doet dat) |
| Systeem-locale nodig | `src/export.py` regel 19 | Werkt toevallig op deze machine, niet gegarandeerd elders |
| Objectief is onzichtbaar | `src/schedule.py` | Config tunen is gokwerk; je ziet niet waarom de solver iets koos |
| Volledige grid-rebuild per edit | `ui/pages/planning_view.py:_render` | Traag en flikkerend; vandaar de `_AG_GRID_FIX_JS` workarounds |

---

## 2. Kernbeslissingen

### 2.1 Eén projectbestand

Alles in één document: `Lesgeefplanning 2026-2027.lesplan` (JSON binnenin, UTF-8).
Seizoenen, weekrooster, alle lessen met hun status en toewijzingen, de lesgeverslijst, alle
beschikbaarheidsrondes met antwoorden, solver-instellingen.

Waarom JSON en niet SQLite: het is klein (± 25 lesgevers × 150 lessen), inspecteerbaar,
diffbaar, en atomisch te schrijven. Waarom een eigen extensie: het bestand is *het document*
dat je doorgeeft aan je opvolger, en een eigen extensie maakt bestandskoppeling mogelijk.

Excel wordt daarmee puur import/export — geen opslag meer.

### 2.2 Excel-export is een live deelkanaal, geen eindproduct

De geëxporteerde `.xlsx` gaat naar Google Drive en wordt daar als Sheet bekeken door de hele
commissie. De roostermaker maakt daar soms snelle wijzigingen zonder de app bij de hand.
Dat betekent:

* De export **draagt identiteit mee** (`les_id`), zodat terug-importeren exact kan koppelen.
* Terug-importeren is een **samenvoegwizard met diff**, geen overschrijving.
* De layout blijft zoals hij nu is (die is goed en wordt gelezen door mensen).
* De import/export-laag krijgt een interface zodat er later een Google Sheets API-implementatie
  naast kan (niet nu bouwen, wel niet in de weg zitten).

### 2.3 Toewijzingen zijn `vast` of `voorstel`

Dit is de belangrijkste modelwijziging. Elke toewijzing heeft een `vast: bool`.

* `vast=True` → harde constraint, de solver mag er niet aankomen. Toont een 📌 in de UI.
* `vast=False` → de solver mag het wijzigen, maar betaalt `penalty_wijziging` als hij het
  weghaalt.

Hiermee wordt "Auto-fill" veilig en herhaalbaar, en "herplan alleen de rest van het seizoen"
valt er gratis uit. "Reset + Auto-fill" als enige uitweg verdwijnt.

### 2.4 Scope is één expliciet begrip, drie keer gebruikt

```
Scope = (seizoen_ids?, van?, tot?, alleen_toekomst)
```

Dezelfde scope bepaalt: welke lessen de beschikbaarheidsronde uitvraagt, wat de solver mag
wijzigen, en wat het gezondheidspaneel analyseert. Hij staat bovenin beeld en wordt als
gemarkeerde band in de kalender getekend, zodat nooit onduidelijk is wat een knop gaat raken.

### 2.5 Peildatum in plaats van `date.today()`

`peildatum: date | None` (None = vandaag). Lessen vóór de peildatum zijn "geweest": ze worden
niet gewijzigd, maar **tellen wel mee** in de werkverdeling en in de weekconflicten. Dat is de
fix voor de openstaande TODO-regel.

### 2.6 UI: NiceGUI, zonder AG Grid

**Beslissing: we blijven bij NiceGUI en gooien AG Grid eruit.**

Overwogen alternatief was FastAPI + React/TypeScript. Dat geeft meer controle, maar kost een
tweede taal, een build-chain en een veel lastiger overdracht aan een niet-informaticus die dit
volgend jaar moet onderhouden. De schaal is klein: een scope is doorgaans 10–40 lessen, dus
native NiceGUI-componenten per rij zijn ruim snel genoeg.

AG Grid gaat er wel uit. De huidige integratie vecht terug: JS als strings, `_AG_GRID_FIX_JS`
workarounds, en een volledige rebuild bij elke celwijziging. In plaats daarvan bouwen we een
`LessonRow`-component en houden we een `dict[les_id, LessonRow]` bij, zodat één edit één rij
hertekent.

De kern (`model/`, `domain/`, `planner/`, `exchange/`) is UI-onafhankelijk. Als de UI-keuze
later toch tegenvalt, is alleen `ui/` weg te gooien.

### 2.7 Distributie: dubbelklikbare .exe

Primair: één Windows `.exe` (PyInstaller, gebouwd in GitHub Actions, gekoppeld aan een GitHub
Release). Overdracht wordt "download dit bestand". Aandachtspunten die in PLAN.md terugkomen:
ortools maakt de bundel groot (100 MB+), en een niet-ondertekende exe geeft een
SmartScreen-waarschuwing — die moet met screenshot op de releasepagina uitgelegd worden.

Secundair, gedocumenteerd voor ontwikkelaars: `uv run lesgeefplanner`.

---

## 3. Datamodel

Alle modellen in `src/lesgeefplanner/model/`. Pydantic v2. Ids zijn `uuid4().hex` strings,
gegenereerd bij aanmaak, **nooit hergebruikt of hergenereerd**.

### 3.1 Project (`model/project.py`)

```python
class Project(BaseModel):
    schema_version: int = 1
    id: str
    naam: str                              # "Lesgeefplanning 2026-2027"
    seizoenen: list[Seizoen] = []
    weekrooster: list[WeekSlot] = []       # standaard; seizoen kan overschrijven
    lesgevers: list[Lesgever] = []
    lessen: list[Les] = []
    rondes: list[Ronde] = []
    solver_config: SolverConfig = SolverConfig()
    werkblad: Werkblad = Werkblad()        # UI-state die je wilt bewaren
```

`Werkblad` bevat: laatst gebruikte `Scope`, `peildatum_override: date | None`,
`laatste_export_pad: str | None`. Bewust onderdeel van het document zodat je bij heropenen
terugkomt waar je was.

Alle lijsten zijn plat; onderlinge relaties lopen via id. Voeg **geen** geneste objecten toe
die elders ook bestaan (de huidige `Les.seizoen: Seizoen` is zo'n duplicaat en veroorzaakt de
nep-seizoenen bij Excel-import).

### 3.2 Lesgever (`model/entities.py`)

```python
class Lesgever(BaseModel):
    id: str
    naam: str                      # volledige naam, ALTIJD ongewijzigd bewaren
    ervaring_jaren: int = 0
    actief: bool = True
    email: str | None = None
    notitie: str = ""
```

**Let op:** de huidige `import_lesgevers` *muteert* `lesgever.naam` naar de voornaam als die
uniek is. Dat is weergave-logica die de data aantast. Vervang door een pure functie:

```python
def display_names(lesgevers: list[Lesgever]) -> dict[str, str]:
    """Voornaam als die uniek is binnen de lijst, anders de volledige naam.
    Muteert niets."""
```

### 3.3 Seizoen en WeekSlot

```python
class WeekSlot(BaseModel):
    dag: int                  # 0 = maandag ... 6 = zondag
    begin_tijd: time
    eind_tijd: time

class Seizoen(BaseModel):
    id: str
    naam: str
    begin: date
    eind: date                        # inclusief
    weekrooster: list[WeekSlot] | None = None   # None = gebruik project.weekrooster
```

Tijden zijn `time`, geen string. De huidige `Les.tijd: str = "17:00 - 20:00"` wordt overal
opnieuw geparsed (`Les.datetime()` splitst op `-`); dat vervalt.

Formatteren gebeurt uitsluitend in `ui/` en `exchange/` via helpers in `domain/formatting.py`.

### 3.4 Les

```python
class Herkomst(BaseModel):
    """Waar een gegenereerde les vandaan komt. None bij handmatig toegevoegde lessen."""
    seizoen_id: str
    weekslot_index: int

class Toewijzing(BaseModel):
    lesgever_id: str
    vast: bool = False
    bron: Literal["handmatig", "solver", "import"] = "handmatig"

class Les(BaseModel):
    id: str
    datum: date
    begin_tijd: time
    eind_tijd: time
    seizoen_id: str | None = None
    titel: str | None = None                    # "PKursus", "Open Les", "Seizoen Start"
    soort: Literal["regulier", "extra"] = "regulier"
    status: Literal["gaat_door", "vervallen"] = "gaat_door"
    vervallen_reden: str | None = None          # "Beka", "Lustrum Trip"
    herkomst: Herkomst | None = None
    beschermd: bool = False                     # zie 4.1: overleeft hergenereren
    toewijzingen: list[Toewijzing] = []
    notitie: str = ""
```

`beschermd` wordt automatisch `True` zodra de gebruiker de les handmatig aanpast (titel,
status, tijd) of er toewijzingen op zet.

Het begrip *activiteit* verdwijnt. Een activiteit die een les afgelast is gewoon
`status="vervallen", vervallen_reden="Beka"`. Dat maakt de stille-fout-klasse onmogelijk.
Bij migratie melden we activiteiten die nergens op matchten (zie 6.1).

### 3.5 Beschikbaarheid (`model/availability.py`)

Bewust **niet** de huidige positionele matrix (`list[list[str]]`), want die breekt zodra er een
les bij komt of af gaat.

```python
Antwoordwaarde = Literal["ja", "misschien", "nee"]

class RondeVraag(BaseModel):
    index: int          # volgorde in het formulier, 1-based
    les_id: str
    label: str          # exact het label dat in het formulier is gezet

class Antwoord(BaseModel):
    lesgever_id: str
    ingevuld_op: datetime | None = None
    doet_mee: bool = True                       # uit de screeningvraag
    waarden: dict[str, Antwoordwaarde] = {}     # les_id -> waarde

class Ronde(BaseModel):
    id: str
    naam: str                                   # "Voorseizoen 1"
    aangemaakt_op: datetime
    scope: Scope
    bron: Literal["google_forms", "datumprikker", "handmatig"] = "google_forms"
    vragen: list[RondeVraag] = []
    antwoorden: list[Antwoord] = []
```

`vragen` wordt vastgelegd op het moment dat de ronde wordt aangemaakt. Daardoor is import
**op positie** mogelijk en is het labelformaat irrelevant — dat elimineert de locale-afhankelijkheid,
de jaar-gok en de "3 uur marge"-fuzzy match in één klap.

Ontbrekende `les_id` in `waarden` betekent **onbekend**, niet "nee". Dat onderscheid is echt:
"heeft niet gereageerd" is iets anders dan "kan niet".

### 3.6 Scope (`model/scope.py`)

```python
class Scope(BaseModel):
    seizoen_ids: list[str] | None = None   # None = alle seizoenen
    van: date | None = None
    tot: date | None = None
    alleen_toekomst: bool = True

    def bevat(self, les: Les, peildatum: date) -> bool: ...
```

`bevat()` is de enige plek waar scope-logica staat. Volgorde: seizoen-filter → datumbereik →
`alleen_toekomst` (`les.datum >= peildatum`).

### 3.7 SolverConfig (`model/config.py`)

Bestaande velden overnemen (die zijn getuned en werken), plus twee nieuwe:

```python
class SolverConfig(BaseModel):
    lesgever_minimum: int = 2
    lesgever_maximum: int = 3
    lesgever_bonus: float = 3
    penalty_lesgever_tekort: float = 10
    penalty_misschien: float = 8
    penalty_geen_ervaren_lesgever: float = 5
    penalty_meerdere_lessen_per_week: float = 8
    richtlijn_lessen_per_week: float = 0.4
    penalty_boven_richtlijn: float = 4
    penalty_onder_richtlijn: float = 2
    penalty_verdeling_stappen: list[float] = [1, 2, 3, 4, 5]
    penalty_wijziging: float = 6          # NIEUW: kosten voor het losbreken van een
                                          # bestaande, niet-vaste toewijzing
    max_rekentijd_seconden: float = 30    # NIEUW: solver-timeout
```

---

## 4. Moeilijke onderdelen, uitgeschreven

Dit zijn de zeven plekken waar het misgaat als je improviseert. Volg deze beschrijvingen
letterlijk.

### 4.1 Kalender genereren en hergenereren (`domain/calendar.py`)

Lessen worden **gematerialiseerd** in `project.lessen` — het zijn de objecten die de gebruiker
bewerkt. Maar ze moeten opnieuw afgeleid kunnen worden als seizoensdatums of het weekrooster
wijzigen, zonder handwerk te wissen.

```python
def gewenste_lessen(project: Project) -> dict[LesSleutel, Herkomst]:
    """Bereken welke reguliere lessen zouden moeten bestaan.
    LesSleutel = (seizoen_id, datum, begin_tijd)."""
```

Algoritme, per seizoen:
1. `rooster = seizoen.weekrooster if seizoen.weekrooster is not None else project.weekrooster`
   — let op: een **lege lijst** is een geldige keuze (zie PKursus in de huidige
   `planning.yml`, `weekrooster: []`), dus test op `is not None`, niet op truthiness.
2. Itereer weken vanaf de maandag op/voor `seizoen.begin` t/m `seizoen.eind`.
3. Voor elk `WeekSlot`: `datum = week_maandag + timedelta(days=slot.dag)`.
4. Neem op als `seizoen.begin <= datum <= seizoen.eind`.

Overlappende seizoenen: als twee seizoenen dezelfde `(datum, begin_tijd)` opleveren, hoort dat
bij het **eerste** seizoen in `project.seizoenen` en genereert het tweede daar niets. Meld dit
als bevinding `seizoenen_overlappen`.

```python
@dataclass
class KalenderDiff:
    toe_te_voegen: list[Les]
    te_verwijderen: list[Les]           # veilig: geen toewijzingen, niet beschermd
    conflicten: list[tuple[Les, str]]   # zou verdwijnen maar heeft werk erin

def bereken_kalender_diff(project: Project) -> KalenderDiff: ...
def pas_kalender_diff_toe(project: Project, diff: KalenderDiff,
                          geaccepteerd: set[str]) -> None: ...
```

Regels:
* Alleen lessen met `soort == "regulier"` en `herkomst is not None` doen mee. Extra lessen en
  handmatig toegevoegde lessen worden **nooit** aangeraakt.
* Bestaande lessen die nog steeds gewenst zijn: **niet aanraken**. Niet de titel, niet de
  status, niet de toewijzingen, ook niet als de tijd in het weekrooster is gewijzigd —
  behalve als `beschermd == False`, dan mag de tijd bijgewerkt worden.
* Een les die zou verdwijnen maar `toewijzingen` heeft of `beschermd` is, gaat naar
  `conflicten`, nooit direct naar `te_verwijderen`.
* De UI toont de diff met vinkjes per regel; `pas_kalender_diff_toe` past alleen de aangevinkte
  ids toe.

Dit wordt **nooit** automatisch uitgevoerd. Altijd via de dialoog.

### 4.2 De solver (`planner/`)

Poort `src/schedule.py` — de constraint-opzet is goed en getuned, dus wijzig de *penalties*
niet. Wat wél verandert: de interface, wat er meetelt, en dat het resultaat uitlegbaar is.

```python
# planner/request.py
@dataclass
class PlanRequest:
    lessen_in_scope: list[Les]      # status == gaat_door, in scope, datum >= peildatum
    lessen_context: list[Les]       # ALLE andere gaat_door lessen in dezelfde seizoenen,
                                    # inclusief het verleden — nodig voor telling
    lesgevers: list[Lesgever]       # alleen actief == True en doet_mee == True
    beschikbaarheid: dict[tuple[str, str], Antwoordwaarde]   # (lesgever_id, les_id)
    config: SolverConfig
    peildatum: date

# planner/result.py
@dataclass
class PlanResult:
    status: Literal["optimaal", "haalbaar", "onhaalbaar"]
    minimum_afgedwongen: bool             # of de harde-minimum-poging lukte
    toewijzingen: dict[str, list[str]]    # les_id -> [lesgever_id]
    score: float
    verdeling: dict[str, float]           # categorie -> bijdrage aan de score
    per_les: dict[str, list[Uitleg]]      # les_id -> waarom deze keuze
    rekentijd: float
```

**Variabelen.** `x[g, l]` BoolVar voor elke `(lesgever, les in scope)` waarvoor
`beschikbaarheid in {"ja", "misschien"}` **of** er een bestaande toewijzing met `vast=True` is.
Bij `beschikbaarheid == "onbekend"` **geen** variabele aanmaken (onbekend ≠ beschikbaar).

**Harde constraints.**
* Vaste toewijzing → `model.Add(x[g,l] == 1)`. Dit geldt ook als de beschikbaarheid "nee" is.
* `sum_g x[g,l] <= config.lesgever_maximum` per les.
* Eerste poging: `sum_g x[g,l] >= config.lesgever_minimum` per les. Bij `INFEASIBLE` opnieuw
  bouwen met dit als soft constraint (zoals nu) en `minimum_afgedwongen=False` teruggeven.

**Zachte termen.** Elke term wordt geregistreerd via een helper, zodat de verdeling na afloop
berekend kan worden:

```python
class TermCollector:
    def add(self, categorie: str, coefficient: float,
            var, les_id: str | None = None, lesgever_id: str | None = None) -> None: ...
    def objective(self): ...            # sum(coefficient * var)
    def breakdown(self, solver) -> dict[str, float]: ...
```

Categorieën: `tekort`, `bezetting_bonus`, `misschien`, `geen_ervaren`, `week_conflict`,
`boven_richtlijn`, `onder_richtlijn`, `wijziging`.

**De drie inhoudelijke wijzigingen ten opzichte van nu:**

1. **Weekconflicten tellen context mee.** Nu telt alleen wat in scope zit. Als iemand zaterdag
   al vaststaat (verleden of buiten scope), moet zondag in dezelfde week nog steeds pijn doen:

   ```
   vast_in_week[g, w] = aantal lessen in lessen_context in ISO-week w waar g op staat
   extra[g, w] >= vast_in_week[g, w] + sum(x[g, l] for l in scope in week w) - 1
   extra[g, w] >= 0
   term: penalty_meerdere_lessen_per_week * extra[g, w]
   ```

2. **Werkverdeling telt reeds gegeven lessen mee.** Dit is de fix voor de TODO.

   ```
   weken_in_seizoen = aantal unieke ISO-weken met een gaat_door les in dat seizoen
                      (over lessen_in_scope + lessen_context samen)
   doel[g] = max(1, round(config.richtlijn_lessen_per_week * weken_in_seizoen))
   reeds[g] = aantal lessen in lessen_context waar g op staat
   totaal[g] = reeds[g] + sum(x[g, l] for l in scope)
   ```

   Daarna de bestaande trapsgewijze boven/onder-penalty op `totaal[g]` versus `doel[g]`,
   ongewijzigd overgenomen uit `src/schedule.py`.

   Bij meerdere seizoenen in scope: bereken `doel` en `reeds` **per seizoen** en tel de
   penalties op. Meng seizoenen niet.

3. **Wijzigingskosten.** Voor elke bestaande toewijzing met `vast == False` op een les in
   scope: `term("wijziging", config.penalty_wijziging, 1 - x[g,l])`. Dus alleen het *weghalen*
   van een bestaande toewijzing kost; iemand toevoegen aan een lege plek niet. Vervangen kost
   automatisch, want dat is weghalen + toevoegen.

**Solverinstellingen.**
```python
solver.parameters.max_time_in_seconds = config.max_rekentijd_seconden
solver.parameters.num_search_workers = 1     # determinisme: twee keer draaien = zelfde
solver.parameters.random_seed = 0            # antwoord. Belangrijker dan snelheid hier.
```

**Uitleg per les.** Na het oplossen, voor elke les in scope: verzamel de termen die aan die
`les_id` hangen en die niet-nul bijdragen, plus per gekozen lesgever hun beschikbaarheidswaarde
en hun `totaal[g]` versus `doel[g]`. Dat voedt het inspectiepaneel.

**De solver muteert niets.** Hij krijgt data, geeft een `PlanResult` terug. De aanroeper zet
dat om in een voorstel-diff die de gebruiker accepteert of verwerpt. Dit is anders dan nu, waar
`schedule_lessons` de `Les`-objecten ter plekke aanpast.

### 4.3 Excel-export met identiteit (`exchange/excel_export.py`)

Poort `src/export.py` — de opmaak blijft zoals hij is (mensen lezen dit blad). Toevoegingen:

* Kolom A wordt `Code` met de eerste 8 tekens van `les_id`, breedte ~2, lettergrootte 8, grijs.
  **Niet verbergen** — een verborgen kolom overleeft de reis door Google Sheets niet
  betrouwbaar en mensen verwijderen wat ze niet snappen minder snel dan wat ze niet zien.
  Zet er een kolomtoelichting bij: "niet verwijderen — nodig om terug te lezen".
* Een tweede werkblad `_meta` met: `project_id`, `schema_version`, `geexporteerd_op`,
  `scope`, en een tabel `les_id | rij | datum | begin_tijd`. Dit blad mag wél verborgen
  worden (`worksheet.hide()`); als iemand het weggooit, valt de import terug op kolom A en
  daarna op datum+tijd.
* `locale.setlocale` verdwijnt. Nederlandse dag- en maandnamen komen uit een tabel in
  `domain/formatting.py`.

Vervallen lessen blijven zoals nu: gemergde cel met "Geen les" plus de reden erbij
(`"Geen les — Beka"`), grijs en cursief.

### 4.4 Excel terug-importeren als samenvoeging (`exchange/excel_import.py`)

Dit is nieuw en essentieel: de Google Sheet is een bewerkingsoppervlak.

```python
@dataclass
class Wijziging:
    les_id: str
    soort: Literal["toegevoegd", "verwijderd", "status", "titel", "tijd"]
    lesgever_id: str | None
    oud: str
    nieuw: str
    zekerheid: Literal["exact", "voorstel"]

def lees_sheet(pad: Path, project: Project) -> tuple[list[Wijziging], list[NaamProbleem]]:
```

Koppelvolgorde per rij, stop bij de eerste die lukt:
1. `_meta`-blad aanwezig en `project_id` klopt → koppel op `les_id`.
2. Kolom `Code` aanwezig → koppel op id-prefix (controleer op uniciteit binnen het project).
3. Val terug op `(datum, begin_tijd)`. Bij meerdere treffers of geen: markeer de rij als
   niet-koppelbaar en toon hem apart.

Namen in de lesgeverkolommen zijn door mensen getypt. Los ze op met `domain/names.py`:

```python
def stel_voor(naam: str, lesgevers: list[Lesgever]) -> list[tuple[Lesgever, float]]:
    """Gerangschikte suggesties, score 0..1. Vergelijkt volledige naam, voornaam,
    en voornaam-tegen-voornaam. Beslist NOOIT zelf."""
```
Score ≥ 0.99 (exacte match op volledige naam of op unieke voornaam) → `zekerheid="exact"`.
Alles daaronder → `zekerheid="voorstel"` en de gebruiker kiest in de wizard, met de optie
"nieuwe lesgever aanmaken" of "regel overslaan".

De UI toont het resultaat als lijst met vinkjes, gegroepeerd per les, met per regel
"oud → nieuw". Alleen aangevinkte wijzigingen worden toegepast. Toegepaste wijzigingen krijgen
`bron="import"` en `vast=True` — iemand heeft ze immers bewust met de hand gezet.

### 4.5 Beschikbaarheidsrondes (`exchange/forms_*.py`)

**Formulier aanmaken.** De app genereert een Google Apps Script dat de gebruiker één keer
plakt op script.google.com en uitvoert. Dat vermijdt OAuth-configuratie volledig.

```python
def genereer_apps_script(ronde: Ronde, project: Project) -> str:
```
Het script maakt:
1. Een dropdown "Wie ben je?" met alle actieve lesgevers als opties — **geen vrije tekst**,
   dat elimineert naamfuzzy bij import volledig.
2. Optioneel een screeningvraag "Wil je dit seizoen ingeroosterd worden?" (ja/nee). Bij "nee"
   springt het formulier naar het einde (`setGoToPage(FormApp.PageNavigationType.SUBMIT)`).
   **Niet nu bouwen**, wel het datamodel (`Antwoord.doet_mee`) er alvast op inrichten.
3. Eén meerkeuzevraag per les, titel `"{label} #{index}"`, opties Ja / Misschien / Nee.

De `#{index}`-suffix is de ankering: import koppelt op index uit `Ronde.vragen`, niet op het
label. Zo maakt het niet uit hoe de datum geformatteerd is of dat iemand vragen herschikt.

De UI toont het script in een kopieerbaar blok met vier genummerde stappen ernaast, plus een
handmatig alternatief (kopieerbare lijst met labels) voor wie het script niet vertrouwt.

**Antwoorden importeren.**
```python
def lees_forms_export(pad: Path, ronde: Ronde, project: Project) -> ImportResultaat:
```
1. Kolomkoppen lezen. Zoek in elke kop naar `#(\d+)`. Gevonden → koppel via
   `Ronde.vragen[index].les_id`.
2. Geen `#n` gevonden (handgemaakt formulier) → val terug op het parsen van het label met de
   locale-vrije maandtabel, en koppel op `(datum, begin_tijd)`. Toon expliciet welke kolommen
   zo gekoppeld zijn zodat de gebruiker het kan nakijken.
3. Naamkolom: als de waarden exact overeenkomen met roosternamen (dropdown gebruikt) → klaar.
   Anders `domain/names.py` + resolutiewizard.
4. Lege cel = **onbekend**, niet "nee". (De huidige code doet `fillna("Nee")`; dat maakt
   "vergeten in te vullen" ononderscheidbaar van "kan niet".)
5. Meerdere reacties van dezelfde persoon: neem de laatste op `ingevuld_op`, en meld het.

Datumprikker-import (`exchange/datumprikker_import.py`) komt later en levert exact hetzelfde
`ImportResultaat` op. Bouw daarom in fase 6 al de gedeelde `ImportResultaat`-vorm, ook al is er
maar één implementatie.

### 4.6 Opslaan, undo en herstel (`store/`)

```python
class Document:
    """Bezit het Project, de undo-stack en het bestandspad."""
    def open(pad: Path) -> Document
    def nieuw(naam: str) -> Document
    def opslaan(self, pad: Path | None = None) -> None
    def muteer(self, beschrijving: str) -> ContextManager[Project]
    def ongedaan_maken(self) -> str | None      # geeft de beschrijving terug
    def opnieuw(self) -> str | None
```

`muteer()` is de **enige** manier waarop het project verandert:

```python
with doc.muteer("Anne toegevoegd aan 19 april") as project:
    project.lessen[3].toewijzingen.append(...)
```
De context manager maakt vooraf een snapshot (`project.model_dump_json()`), voert het blok uit,
duwt de snapshot op de undo-stack (max 50), leegt de redo-stack en markeert het document als
gewijzigd. Volledige snapshots zijn bij deze omvang (± 200 kB) prima en veel minder foutgevoelig
dan omgekeerde operaties.

Opslaan is atomisch: schrijf naar `<naam>.lesplan.tmp`, `flush` + `os.replace()`. Autosave 30 s
na de laatste wijziging. Daarnaast bij elke opslag een kopie in
`<map>/.lesgeefplanner-backups/<naam>-<timestamp>.lesplan`, laatste 10 bewaren.

Migraties: `store/migrations.py` met `MIGRATIES: dict[int, Callable[[dict], dict]]`. Bij het
openen `schema_version` lezen en stapsgewijs ophogen. Ook bij versie 1 al aanwezig, leeg — dan
staat het framework er als het nodig wordt.

### 4.7 Incrementeel renderen (`ui/planning_view.py`)

Het probleem met de huidige view: `_render()` wist en herbouwt de hele grid bij elke edit.

```python
class PlanningView:
    def __init__(self, doc: Document): 
        self._rows: dict[str, LessonRow] = {}
    def rebuild(self) -> None:        # alleen bij scope-wissel of nieuw project
    def refresh_les(self, les_id: str) -> None:    # één rij
    def refresh_lessen(self, les_ids: Iterable[str]) -> None
```

Na een celwijziging roep je `refresh_les(les_id)` aan plus `refresh_les` voor de lessen in
dezelfde week (die kunnen een weekconflict-badge krijgen of verliezen). Nooit `rebuild()`.

Toewijzen gebeurt met **klikken, niet slepen**: klik op een lesgeverslot → menu met alle
lesgevers gegroepeerd op Ja / Misschien / Onbekend / Nee, elk met hun huidige belasting
("Anne — 3/4 lessen"), plus 📌 om vast te zetten en ✕ om te wissen. Slepen is later eventueel
een toevoeging, maar klikken is nauwkeuriger en veel eenvoudiger goed te krijgen.

---

## 5. Analyse in plaats van een tekstrapport (`domain/analysis.py`)

```python
class Bevinding(BaseModel):
    code: str
    ernst: Literal["fout", "waarschuwing", "info"]
    titel: str                   # kort, Nederlands, voor de lijst
    uitleg: str                  # één zin, wat eraan te doen
    les_id: str | None = None
    lesgever_id: str | None = None
    waarde: float | None = None

def analyseer(project: Project, scope: Scope, peildatum: date) -> list[Bevinding]:
```

Codes die geïmplementeerd moeten worden:

| code | ernst | wanneer |
|---|---|---|
| `les_niet_ingevuld` | fout | gaat door, in scope, 0 toewijzingen |
| `les_te_weinig_lesgevers` | fout | < `lesgever_minimum` |
| `les_geen_ervaren_lesgever` | waarschuwing | geen enkele toewijzing met `ervaring_jaren >= 1` |
| `les_misschien_gebruikt` | waarschuwing | iemand ingedeeld die "misschien" antwoordde |
| `les_zonder_beschikbaarheid` | waarschuwing | les in scope zit in geen enkele ronde |
| `lesgever_dubbel_in_week` | waarschuwing | ≥ 2 lessen in dezelfde ISO-week |
| `lesgever_boven_richtlijn` | waarschuwing | `totaal > doel` (zie 4.2 voor de definitie) |
| `lesgever_onder_richtlijn` | info | `totaal < doel` |
| `lesgever_niet_gereageerd` | info | actief, maar geen `Antwoord` in de ronde |
| `lesgever_ingedeeld_maar_nee` | fout | ingedeeld terwijl beschikbaarheid "nee" is |
| `seizoenen_overlappen` | waarschuwing | zie 4.1 |
| `les_buiten_seizoen` | info | les valt in geen enkel seizoen |

`domain/report.py` rendert `list[Bevinding]` naar de bestaande platte tekst, zodat "kopieer
rapport voor de commissieapp" blijft werken. De tekstopmaak is dan een *view*, niet de bron.

De UI toont dezelfde lijst als klikbare items: klikken scrolt naar de les of persoon en licht
die op. Daarnaast een balkdiagram belasting-per-persoon met de doelband erin, en het
score-overzicht uit `PlanResult.verdeling` ("waarom deze score?").

---

## 6. Migratie van de huidige situatie

### 6.1 Eenmalige importer

`exchange/legacy_import.py`, aangeroepen vanuit het startscherm als "Importeer oude opzet":

```python
def importeer_oude_opzet(planning_yml: Path, lesgevers_xlsx: Path | None,
                         planning_xlsx: Path | None) -> tuple[Project, list[str]]:
    """Bouwt een Project uit de oude bestanden. Tweede returnwaarde is een lijst
    Nederlandse waarschuwingen om aan de gebruiker te tonen."""
```

Regels:
* `seizoenen`, `weekrooster` → direct over. `weekrooster: []` blijft een lege lijst
  (niet `None`).
* `extra-lessen` → `Les(soort="extra", titel=..., herkomst=None, beschermd=True)`.
* `activiteiten` → zoek de gegenereerde les op die datum.
  * `les-gaat-door: false` → `status="vervallen"`, `vervallen_reden=naam`.
  * `les-gaat-door: true` → `titel=naam`, en `tijd` overnemen als die is opgegeven.
  * **Geen match** → waarschuwing: `"Activiteit 'Lustrum Trip' op 2026-05-16 hoort bij geen
    enkele les en is overgeslagen."` Dit is precies het geval dat nu stil faalt.
* `lesgevers.xlsx` → `Lesgever` met volledige naam bewaard (niet inkorten).
* `planning.xlsx`, indien meegegeven → toewijzingen overnemen via naamresolutie, allemaal met
  `vast=True` en `bron="import"`.
* Beschikbaarheid uit oude forms-exports wordt **niet** gemigreerd. Te weinig waarde, te veel
  randgevallen. Wel documenteren.

### 6.2 Wat er met de oude code gebeurt

`src/` (de losse modules) en `ui/` van de huidige branch blijven staan tot en met fase 8, als
referentie. Fase 10 verwijdert ze. `main.py` verdwijnt; de CLI komt terug als
`lesgeefplanner --export <bestand>` als dat gewenst blijkt, maar is geen doel op zich.

---

## 7. Mappenstructuur

```
src/lesgeefplanner/
  __init__.py
  __main__.py              # entry point: server starten, browser openen
  model/
    __init__.py
    project.py             # Project, Werkblad
    entities.py            # Lesgever, Seizoen, WeekSlot, Les, Toewijzing, Herkomst
    availability.py        # Ronde, RondeVraag, Antwoord
    scope.py               # Scope
    config.py              # SolverConfig
  store/
    document.py            # Document, muteer(), undo/redo, autosave
    migrations.py
  domain/
    calendar.py            # genereren + KalenderDiff
    analysis.py            # Bevinding, analyseer()
    report.py              # tekstrapport uit bevindingen
    names.py               # stel_voor(), display_names()
    formatting.py          # NL dag-/maandnamen, tijd- en datumopmaak
  planner/
    request.py             # PlanRequest
    result.py              # PlanResult, Uitleg
    terms.py               # TermCollector
    solve.py               # bouw CP-SAT model + oplossen
  exchange/
    excel_export.py
    excel_import.py        # samenvoegwizard-logica
    roster_import.py       # lesgevers uit xlsx
    forms_script.py        # Apps Script generator
    forms_import.py
    legacy_import.py
    types.py               # ImportResultaat, Wijziging, NaamProbleem
  ui/
    app.py                 # layout, header, scope-balk
    startscherm.py
    planning_view.py       # het middenpaneel, altijd zichtbaar
    inspector.py           # rechterpaneel: gezondheid / les / persoon
    stappen.py             # linkerrail met voortgang
    dialogen/
      jaarplanning.py      # seizoenen + weekrooster (vervangt de YAML)
      lesgevers.py
      rondes.py
      solver_config.py
      diff_dialoog.py      # herbruikbaar: kalenderdiff, planvoorstel, excel-merge
tests/
  ...
```

`exchange` heet bewust niet `io` (dat botst visueel met de stdlib-module).

`dialogen/diff_dialoog.py` is één herbruikbaar component voor drie situaties: kalender
hergenereren, een solvervoorstel accepteren, en een Excel-merge. Alle drie hebben dezelfde
vorm: lijst met regels, vinkje per regel, "oud → nieuw", knoppen Toepassen / Annuleren. Bouw
het één keer.

---

## 8. Testen

Minimaal, maar niet-onderhandelbaar op deze punten:

* `domain/calendar.py` — generatie inclusief `weekrooster: []`, seizoensgrenzen op een
  maandag/zondag, overlappende seizoenen, en diff met een beschermde les.
* `planner/solve.py` — een klein scenario (4 lessen, 5 lesgevers) waarin gecontroleerd wordt
  dat: vaste toewijzingen blijven staan; context-lessen meetellen in weekconflict en
  werkverdeling; wijzigingskosten voorkomen dat een bestaand rooster onnodig omgegooid wordt;
  `verdeling` optelt tot `score`.
* `exchange/excel_export.py` + `excel_import.py` — round-trip: exporteer, wijzig een naam in
  het bestand, importeer, verwacht precies één `Wijziging`.
* `store/document.py` — muteer/undo/redo, atomisch opslaan, migratie van versie 0 naar 1.
* `domain/names.py` — dat "Jan" **geen** exacte match op "Jen" oplevert.

`pytest`. Geen UI-tests.

---

## 9. Bewust niet nu

* Google Sheets API-integratie (wel de laag ervoor zo laten dat het erbij kan).
* Datumprikker-import (`ImportResultaat` alvast gedeeld maken).
* De screeningvraag in het formulier (`Antwoord.doet_mee` staat er al).
* Slepen van lesgevers tussen lessen.
* Meerdere gebruikers / online delen. De Excel-export in Drive dekt de kijkbehoefte.
* Ervaring die *tijdens* het seizoen wordt opgebouwd meewegen in `geen_ervaren`. Het
  datamodel staat het toe; de constraint zou dan per les een andere ervarenset gebruiken.
  Zie PLAN.md fase 11 als optioneel.
