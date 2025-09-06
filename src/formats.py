import xlsxwriter

def add_formats(workbook: xlsxwriter.workbook) -> dict[str, xlsxwriter.format]:

    return {
        "header": workbook.add_format({"align": "center", "bold": True}),
        "center": workbook.add_format({"align": "center", "valign": "vcenter"}),
        "top-left": workbook.add_format({"align": "left", "valign": "top"}),
    }