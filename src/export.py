"""Exporteert de planning naar een excel file.
| Naseizoen 1 | Week 36 | Woensdag 3 Sept | 17:00 - 20:00 | <4 kolommen voor lesgevers> | <naam van les> |
"""
import xlsxwriter
from datetime import date
import locale
from .models import Planning, Les

AANTAL_LESGEVERS = 3
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

def write_les(worksheet: xlsxwriter.worksheet, workbook: xlsxwriter.workbook, les: Les, row: int, border_style: int):
    
    # Shared formatting for row
    fmt = {"top": border_style}
    if get_week_number(les.datum) % 2 == 0:
        fmt["bg_color"] = "#DCE6F1"   
    else:
        fmt["bg_color"] = "#f0f0f0"
    if not les.gaat_door:
        fmt["font_color"] = "gray"
        fmt["italic"] = True
    
    format = workbook.add_format(fmt)
    l_border_format = workbook.add_format({"left": 1} | fmt)
    lr_border_format = workbook.add_format({"left": 1, "right": 1} | fmt)

    # Write all cells, including empty ones for formatting
    if les.seizoen:
        worksheet.write_string(row, COL_MAP["seizoen"], les.seizoen.naam, lr_border_format)
    else:
        worksheet.write_string(row, COL_MAP["seizoen"], "", lr_border_format)
    worksheet.write_number(row, COL_MAP["week"], get_week_number(les.datum), lr_border_format)
    worksheet.write_string(row, COL_MAP["datum"], les.datum.strftime("%A %d %b"), l_border_format)
    worksheet.write_string(row, COL_MAP["tijd"], les.tijd, format)
    if les.naam:
        worksheet.write_string(row, COL_MAP["naam"], les.naam, lr_border_format)
    else:
        worksheet.write_string(row, COL_MAP["naam"], "", lr_border_format)
    if not les.gaat_door:
        links = col_to_char(COL_MAP["lesgevers"][0])
        rechts = col_to_char(COL_MAP["lesgevers"][-1])
        range_spec = f'{links}{row+1}:{rechts}{row+1}'
        format = workbook.add_format({"align": "center", "left": 1} | fmt)
        worksheet.merge_range(range_spec, "Geen les", format)
    else:
        lesgevers_namen = []
        if les.lesgevers:
            for lesgever in les.lesgevers:
                lesgevers_namen.append(lesgever.naam)
        lesgevers_namen = lesgevers_namen + [""] * (AANTAL_LESGEVERS - len(lesgevers_namen))
        for lesgever, col in zip(lesgevers_namen, COL_MAP["lesgevers"]):
            worksheet.write(row, col, lesgever, l_border_format if col == COL_MAP["lesgevers"][0] else format)


def export_planning(planning: Planning, excel_path: str):
    workbook = xlsxwriter.Workbook(excel_path)
    worksheet = workbook.add_worksheet("Planning")
    

    # Write header
    header_format = workbook.add_format({"align": "center", "bold": True, "top": 2})
    worksheet.write_string(0, COL_MAP["seizoen"], "Seizoen", header_format)
    worksheet.write_string(0, COL_MAP["week"], "Week", header_format)
    worksheet.write_string(0, COL_MAP["datum"], "Datum", header_format)
    worksheet.write_string(0, COL_MAP["tijd"], "Tijd", header_format)
    lesgevers_range_spec = f'{col_to_char(COL_MAP["lesgevers"][0])}1:{col_to_char(COL_MAP["lesgevers"][-1])}1'
    worksheet.merge_range(lesgevers_range_spec, "Lesgevers", header_format)
    worksheet.write_string(0, COL_MAP["naam"], "Info", header_format)

    # Vind groepen van seizoen en week    
    seizoen_ranges = find_ranges([les.seizoen.naam for les in planning.lessen])
    week_ranges = find_ranges([get_week_number(les.datum) for les in planning.lessen])

    # Schrijf elke les op eigen rij
    planning.lessen.sort(key=lambda x: (x.datum, x.tijd))
    for row, les in enumerate(planning.lessen):
        border_style = 0
        if row in [r[0] for r in week_ranges]:
            border_style = 1
        if row in [r[0] for r in seizoen_ranges]:
            border_style = 2
        write_les(worksheet, workbook, les, row + HEADER_ROWS, border_style)
    
    # teken een horizontale lijn helemaal onderaan
    for col in range(COL_MAP["naam"]+1):
        row = len(planning.lessen) + HEADER_ROWS 
        worksheet.write_string(row, col, "", workbook.add_format({"top": 2}))
        
    # Mooi maken
    merge_cells(worksheet, COL_MAP["seizoen"], seizoen_ranges, [les.seizoen.naam for les in planning.lessen],
                 workbook.add_format({"align": "center", "valign": "top", "bold": True, "top": 2}))
    merge_cells(worksheet, COL_MAP["week"], week_ranges, [get_week_number(les.datum) for les in planning.lessen],
                 workbook.add_format({"align": "center", "valign": "top", "bold": True, "top": 1}))

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
    return list(zip(borders[:-1], borders[1:]))

def merge_cells(worksheet: xlsxwriter.worksheet, column: int, ranges: list[int], values: list[str], format: xlsxwriter.format):
    for top, bottom in ranges:
        # merge alle rijen met dezelfde waarde 
        if bottom - top > 1:
            start_row = top + HEADER_ROWS + 1
            end_row = bottom + HEADER_ROWS
            range_spec = f'{col_to_char(column)}{start_row}:{col_to_char(column)}{end_row}'
            worksheet.merge_range(range_spec, values[top], format)


    