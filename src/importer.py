"""Importeert excel bestanden naar models. Voor zowel planning, lesgevers als datumprikker."""
import pandas as pd
from .models import Lesgever, Les, DatumPrikker
from Levenshtein import distance as levenshtein_distance

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
            planning_ids_distances = [(pid, Levenshtein.distance(dapri_les, pid)) for pid in planning_ids]
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