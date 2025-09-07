"""Importeert excel bestanden naar models. Voor zowel planning, lesgevers als datumprikker."""
import pandas as pd
from datetime import datetime
from .models import Lesgever, Les, DatumPrikker, Planning
from .config import Seizoen
from Levenshtein import distance as levenshtein_distance
import locale

def import_lesgevers(lesgevers_path: str) -> list[Lesgever]:
    """Importeert lesgevers uit een xlsx bestand. Sheet 'Lesgevers' wordt gebruikt."""
    xls = pd.ExcelFile(lesgevers_path)
    df = pd.read_excel(xls, sheet_name="Lesgevers")

    # vindt de ervaring kolom, die misschien wel een van exacte naam verandert
    ervaring_kolom = df.columns[df.columns.str.contains("Ervar", case=False)]
    if len(ervaring_kolom) != 1:
        raise ValueError(f"Er is geen enkele kolom met 'Ervar' in de naam, of er zijn er meerdere: {ervaring_kolom}")
    ervaring_kolom = ervaring_kolom[0]

    def row_to_lesgever(row: pd.Series) -> Lesgever:
        actief_string = row["Actief"]
        if actief_string.lower() in ["true", "ja"]:
            actief = True
        elif actief_string.lower() in ["false", "nee"]:
            actief = False
        else:
            raise ValueError(f"Actief string {actief_string} is niet true/false of ja/nee")
        return Lesgever(naam=row["Naam"], ervaring_jaren=row[ervaring_kolom], actief=actief)
    
    return [row_to_lesgever(row) for _, row in df.iterrows()]

def import_datumprikker(datumprikker_path: str, lessen: list[Les], lesgevers: list[Lesgever]) -> DatumPrikker:
    """Matcht de datumprikker excel met de lessen en lesgevers. De output is een DatumPrikker model.
    Het is mogelijk om een datumprikker te gebruiken voor een gedeelte van de lessen die worden meegegeven."""

    # Lees excel bestand in
    df = pd.read_excel(datumprikker_path)
    
    # Lees lessen in het datumprikker bestand, en converteer naar Les.id() format string
    dapri_lessen = df.iloc[3,2:].to_list() # In format 'wo 10 sep 2025\n01:00 - 05:00\nPKursus\n[100%]'
    dapri_lessen = [" ".join(l.split("\n")[:2]).replace(" ", "") for l in dapri_lessen] # in format 'wo10sep202501:00-05:00'
    dapri_lessen_gematcht = match_lessen(dapri_lessen, lessen)

    # Lees lesgevers in het datumprikker bestand
    dapri_lesgevers = df.iloc[4:,0].to_list()
    dapri_lesgevers_gematcht = match_lesgevers(dapri_lesgevers, lesgevers)
    ontbrekende_lesgevers = [l for l in lesgevers if l not in dapri_lesgevers_gematcht]

    # Extraheer beschikbaarheid door direct de matrix te lezen
    beschikbaarheid = df.iloc[4:,2:].values.tolist()
    # check of er niet perongelijk lege cellen tussen zitten
    for row in beschikbaarheid:
        for cell in row:
            if cell == "":
                raise ValueError(f"Er zijn lege cellen tussen in de beschikbaarheid matrix met formaat {len(beschikbaarheid)}x{len(beschikbaarheid[0])}")

    return DatumPrikker(
        lessen=dapri_lessen_gematcht,
        lesgevers_al_ingevuld=dapri_lesgevers_gematcht,
        lesgevers_nog_te_vullen=ontbrekende_lesgevers,
        beschikbaarheid=beschikbaarheid)


def match_lessen(dapri_lessen: list[str], lessen: list[Les]) -> list[Les]:
    """Controleert dat elke les in de datumprikker gematcht kan worden met eentje in de planning.
    Andersom is niet verplicht. Maar wordt wel vermeld."""
    planning_ids = [l.id() for l in lessen]
    dapri_lessen_gematcht = []
    for dapri_les in dapri_lessen:
        if dapri_les not in planning_ids:
            # Find and print the closest match for debugging
            planning_ids_distances = [(pid, levenshtein_distance(dapri_les, pid)) for pid in planning_ids]
            closest_match = min(planning_ids_distances, key=lambda x: x[1])
            print(f"Dichtstbijzijnde match voor '{dapri_les}' is '{closest_match[0]}' (afstand: {closest_match[1]})")
            raise ValueError(f"Les {dapri_les} niet gevonden in planning! Pas de spreadsheet handmatig aan om het conflict op te lossen.")
        dapri_lessen_gematcht.append(lessen[planning_ids.index(dapri_les)])
    for planning_les in planning_ids:
        if planning_les not in dapri_lessen:
            print(f"Let op: Les {planning_les} niet gevonden in de datumprikker. Controleer dat dit wel geregeld wordt.")
    return dapri_lessen_gematcht

def match_lesgevers(dapri_lesgevers: list[str], lesgevers: list[Lesgever]) -> list[Lesgever]:
    """Vervangt datumprikker gebruikersnamen door de volledige naam uit het lesgevers bestand.
    Gebruikt beste fuzzy matching met een threshold. Geeft een foutmelding als een naam ontbreekt."""
    dapri_lesgevers_gematcht = []
    for dapri_lesgever in dapri_lesgevers:
        distances = [distance(dapri_lesgever, lesgever.naam) for lesgever in lesgevers]
        min_distance = min(distances)
        if min_distance < 3:
            dapri_lesgevers_gematcht.append(lesgevers[distances.index(min_distance)])
            if min_distance > 0:
                print(f"Let op: gebruikersnaam {dapri_lesgever} is gekoppeld aan {lesgevers[distances.index(min_distance)].naam}, maar is niet helemaal gelijk.")
        else:
            raise ValueError(f"Gebruikersnaam {dapri_lesgever} niet gevonden in lesgevers bestand! Pas de spreadsheet handmatig aan om het conflict op te lossen.")
    return dapri_lesgevers_gematcht

def distance(naam_dapri, naam_volledig) -> float:
    """Berekent de edit distance tussen twee namen, houdt rekening met dat eventueel alleen de voornaam in de datumprikker is gebruikt.."""
    volledige_match = levenshtein_distance(naam_dapri.lower(), naam_volledig.lower())
    alleen_voornaam = levenshtein_distance(naam_dapri.lower(), naam_volledig.split(" ")[0].lower())
    return min(volledige_match, alleen_voornaam)

def import_planning(excel_path: str, starting_year: int = 2025) -> Planning:
    """Importeert planning uit een xlsx bestand. Sheet 'Planning' wordt gebruikt.
    Gebruikt ffill() alleen voor Seizoen en Week kolommen om merged cells te behandelen.
    
    Args:
        excel_path: Pad naar het Excel bestand
        starting_year: Startjaar voor datums zonder jaar (default: 2025)
        
    Returns:
        Planning object met alle lessen uit de Excel
    """
    
    # Lees Excel bestand in
    df = pd.read_excel(excel_path, sheet_name="Planning")
    
    # Gebruik forward fill alleen voor Seizoen en Week kolommen om merged cells te behandelen
    if "Seizoen" in df.columns:
        df["Seizoen"] = df["Seizoen"].ffill()
    if "Week" in df.columns:
        df["Week"] = df["Week"].ffill()
    
    # Verwachte kolommen gebaseerd op export functie:
    # Seizoen | Week | Datum | Tijd | Lesgever1 | Lesgever2 | Lesgever3 | Info
    expected_columns = ["Seizoen", "Week", "Datum", "Tijd", "Info"]
    lesgever_columns = [col for col in df.columns if col not in expected_columns and not col.startswith("Unnamed")]
    
    # Als er geen expliciete lesgever kolommen zijn, probeer te detecteren
    if not lesgever_columns:
        # Zoek naar kolommen tussen Tijd en Info die lesgevers zouden kunnen zijn
        tijd_idx = df.columns.get_loc("Tijd") if "Tijd" in df.columns else 3
        info_idx = df.columns.get_loc("Info") if "Info" in df.columns else len(df.columns) - 1
        lesgever_columns = [df.columns[i] for i in range(tijd_idx + 1, info_idx)]
    
    lessen = []
    
    for _, row in df.iterrows():
        # Parse datum
        datum_str = row["Datum"]
        if pd.isna(datum_str) or datum_str == "":
            continue  # Skip empty rows
            
        # Probeer verschillende datum formaten
        jaren_verlopen = 0
        datum = None
        for _locale in ["nl_NL", "en_US"]:
            locale.setlocale(locale.LC_TIME, _locale)
            for date_format in ["%A %d %b", "%a %d-%b", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    parsed_date = datetime.strptime(str(datum_str), date_format)
                    # Als alleen dag/maand gegeven, gebruik starting_year en logica voor jaar overgangen
                    if "Y" not in date_format:
                        datum = parsed_date.replace(year=starting_year).date()
                        # Als we al datum hebben gehad en deze datum is eerder in het jaar,
                        # dan zijn we waarschijnlijk in het volgende jaar
                        if lessen and datum < lessen[-1].datum:
                            datum = parsed_date.replace(year=starting_year + jaren_verlopen).date()
                            jaren_verlopen += 1
                    else:
                        datum = parsed_date.date()
                    break
                except ValueError:
                    continue
        if datum is None:
            print(f"Kon datum niet parsen: {datum_str}")
            continue
            
        # Parse tijd
        tijd = str(row["Tijd"]) if not pd.isna(row["Tijd"]) else ""
        
        # Parse seizoen
        seizoen = None
        if not pd.isna(row["Seizoen"]) and row["Seizoen"] != "":
            seizoen_naam = str(row["Seizoen"])
            # Maak een simpele seizoen object - in een echte implementatie zou je 
            # dit kunnen matchen met bestaande seizoenen
            seizoen = Seizoen(naam=seizoen_naam, begin=datum, eind=datum)
        
        # Parse lesgevers
        lesgevers = []
        for col in lesgever_columns:
            if col in row and not pd.isna(row[col]) and str(row[col]).strip() != "":
                lesgever_naam = str(row[col]).strip()
                if lesgever_naam != "Geen les":  # Skip merged "Geen les" cells
                    # Maak een simpele lesgever object
                    lesgever = Lesgever(naam=lesgever_naam, ervaring_jaren=0, actief=True)
                    lesgevers.append(lesgever)
        
        # Parse naam/info
        naam = None
        if not pd.isna(row["Info"]) and str(row["Info"]).strip() != "":
            naam = str(row["Info"]).strip()
        
        # Bepaal of les doorgaat (als er "Geen les" staat, gaat het niet door)
        gaat_door = True
        if any("Geen les" in str(row[col]) for col in lesgever_columns if col in row and not pd.isna(row[col])):
            gaat_door = False
            lesgevers = []  # Clear lesgevers als les niet doorgaat
        
        # Maak Les object
        les = Les(
            datum=datum,
            tijd=tijd,
            naam=naam,
            lesgevers=lesgevers if lesgevers else None,
            gaat_door=gaat_door,
            seizoen=seizoen
        )
        
        lessen.append(les)
    
    return Planning(lessen=lessen)