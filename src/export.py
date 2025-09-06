"""Exporteert de planning naar een excel file.
| Naseizoen 1 | Week 36 | Woensdag 3 Sept | 17:00 - 20:00 | <4 kolommen voor lesgevers> | <naam van les> |
"""
import xlsxwriter
from datetime import date
import locale
from .models import Planning, Les
from .formats import add_formats

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
locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')

def col_to_char(col: int) -> str:
    return chr(65 + col)

def get_week_number(date: date) -> int:
    return date.isocalendar()[1]

def write_les(worksheet: xlsxwriter.worksheet, les: Les, row: int, formats: dict[str, xlsxwriter.format]):
    if les.seizoen:
        worksheet.write_string(row, COL_MAP["seizoen"], les.seizoen.naam)
    worksheet.write_number(row, COL_MAP["week"], get_week_number(les.datum))
    worksheet.write_string(row, COL_MAP["datum"], les.datum.strftime("%A %d %b"))
    worksheet.write_string(row, COL_MAP["tijd"], les.tijd)
    if les.naam:
        worksheet.write_string(row, COL_MAP["naam"], les.naam)
    if not les.gaat_door:
        links = col_to_char(COL_MAP["lesgevers"][0])
        rechts = col_to_char(COL_MAP["lesgevers"][-1])
        range_spec = f'{links}{row+1}:{rechts}{row+1}'
        worksheet.merge_range(range_spec, "Geen les", formats["center"])


def export_planning(planning: Planning, excel_path: str):
    workbook = xlsxwriter.Workbook(excel_path)
    worksheet = workbook.add_worksheet("Planning")
    formats = add_formats(workbook)

    # Write header
    worksheet.write_string(0, COL_MAP["seizoen"], "Seizoen", formats["header"])
    worksheet.write_string(0, COL_MAP["week"], "Week", formats["header"])
    worksheet.write_string(0, COL_MAP["datum"], "Datum", formats["header"])
    worksheet.write_string(0, COL_MAP["tijd"], "Tijd", formats["header"])
    lesgevers_range_spec = f'{col_to_char(COL_MAP["lesgevers"][0])}1:{col_to_char(COL_MAP["lesgevers"][-1])}1'
    worksheet.merge_range(lesgevers_range_spec, "Lesgevers", formats["header"])
    worksheet.write_string(0, COL_MAP["naam"], "Info", formats["header"])

    # Schrijf elke les op eigen rij
    planning.lessen.sort(key=lambda x: (x.datum, x.tijd))
    for row, les in enumerate(planning.lessen):
        write_les(worksheet, les, row + HEADER_ROWS, formats)

        
    # Mooi maken
    seizoen_ranges = find_ranges([les.seizoen.naam for les in planning.lessen])
    week_ranges = find_ranges([get_week_number(les.datum) for les in planning.lessen])
    merge_cells(worksheet, COL_MAP["seizoen"], seizoen_ranges, [les.seizoen.naam for les in planning.lessen], formats["top-left"])
    merge_cells(worksheet, COL_MAP["week"], week_ranges, [get_week_number(les.datum) for les in planning.lessen], formats["top-left"])

    # Autofit columns
    worksheet.autofit()

    workbook.close()

def find_ranges(values: list[str]) -> list[int]:
    borders = []
    last_value = None
    for i, value in enumerate(values):
        if value != last_value:
            borders.append(i)
            last_value = value
    borders.append(len(values))
    return zip(borders[:-1], borders[1:])

def merge_cells(worksheet: xlsxwriter.worksheet, column: int, ranges: list[int], values: list[str], format: xlsxwriter.format):
    for left, right in ranges:
        # merge alle rijen met dezelfde waarde 
        if right - left > 1:
            start_row = left + HEADER_ROWS + 1
            end_row = right + HEADER_ROWS
            range_spec = f'{col_to_char(column)}{start_row}:{col_to_char(column)}{end_row}'
            worksheet.merge_range(range_spec, values[left], format)



    