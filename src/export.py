"""Exporteert de planning naar een excel file.
| Naseizoen 1 | Week 36 | Woensdag 3 Sept | 17:00 - 20:00 | <4 kolommen voor lesgevers> | <naam van les> |
"""
from .models import Planning, Les
import xlsxwriter
from datetime import date

AANTAL_LESGEVERS = 4
COL_MAP = {
    "seizoen": 0,
    "week": 1,
    "datum": 2,
    "tijd": 3,    
    "lesgevers": list(range(4, 4 + AANTAL_LESGEVERS)),
    "naam": 4 + AANTAL_LESGEVERS,
}
HEADER_ROWS = 1

def col_to_char(col: int) -> str:
    return chr(65 + col)

def get_week_number(date: date) -> int:
    return date.isocalendar()[1]

def write_les(worksheet: xlsxwriter.worksheet, les: Les, row: int):
    worksheet.write_string(row, COL_MAP["seizoen"], les.seizoen.naam)
    worksheet.write_number(row, COL_MAP["week"], get_week_number(les.datum))
    worksheet.write_string(row, COL_MAP["datum"], les.datum.strftime("%A %d %b"))
    worksheet.write_string(row, COL_MAP["tijd"], les.tijd)
    if les.naam:
        worksheet.write_string(row, COL_MAP["naam"], les.naam)
    if not les.gaat_door:
        links = col_to_char(COL_MAP["lesgevers"][0])
        rechts = col_to_char(COL_MAP["lesgevers"][-1])
        range_spec = f'{links}{row}:{rechts}{row}'
        worksheet.merge_range(range_spec, "Geen les")


def export_planning(planning: Planning, excel_path: str):
    workbook = xlsxwriter.Workbook(excel_path)
    worksheet = workbook.add_worksheet("Planning")

    # Write header
    worksheet.write_string(0, COL_MAP["seizoen"], "Seizoen")
    worksheet.write_string(0, COL_MAP["week"], "Week")
    worksheet.write_string(0, COL_MAP["datum"], "Datum")
    worksheet.write_string(0, COL_MAP["tijd"], "Tijd")

    # Schrijf elke les op eigen rij
    for row, les in enumerate(planning.lessen):
        write_les(worksheet, les, row + HEADER_ROWS)
        
    # Mooi maken
    pretty_format(worksheet, planning)

    # Autofit columns
    worksheet.autofit()

    workbook.close()

def pretty_format(worksheet: xlsxwriter.worksheet, planning: Planning):
    merge_cells(worksheet, planning)


def merge_cells(worksheet: xlsxwriter.worksheet, planning: Planning):

    # itereer over de kolommen
    for column, getter in [
        (COL_MAP["seizoen"], lambda x: x.seizoen.naam),
        (COL_MAP["week"], lambda x: get_week_number(x.datum))]:
        
        # itereer over de lessen
        last_value = None
        start_index = 0
        
        for i, les in enumerate(planning.lessen+[None]):
            if les is not None:
                value = getter(les)
            else:
                value = None

            # als waarde verandert
            if value != last_value:

                # merge alle rijen met dezelfde waarde (kan dus 1 enkele cell zijn)
                if i - start_index > 1:  # Only merge if there are at least 2 cells
                    start_row = start_index + HEADER_ROWS + 1
                    end_row = i + HEADER_ROWS
                    range_spec = f'{col_to_char(column)}{start_row}:{col_to_char(column)}{end_row}'
                    worksheet.merge_range(range_spec, last_value)

                start_index = i
                last_value = value
 



    