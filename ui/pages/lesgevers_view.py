"""View and edit the lesgevers list, with xlsx upload."""
from pathlib import Path

from nicegui import events, ui

from src.models import Lesgever
from ui.state import state, LESGEVERS_XLSX_PATH


def create_lesgevers_tab():
    ui.label("Lesgevers").classes("text-h6 q-mb-sm")

    status = ui.label("").classes("text-caption q-mt-xs q-mb-sm")

    with ui.row().classes("q-gutter-sm items-center q-mb-md"):
        ui.upload(
            label="Upload lesgevers.xlsx",
            auto_upload=True,
            on_upload=lambda e: _handle_upload(e, grid_container, status),
        ).props('accept=".xlsx,.xls" flat bordered').classes("max-w-xs")

        if LESGEVERS_XLSX_PATH.exists():
            ui.button(
                "Herlaad van schijf",
                icon="refresh",
                on_click=lambda: _reload_from_disk(grid_container, status),
            ).props("flat")

    grid_container = ui.column().classes("w-full")
    _render_grid(grid_container)

    if state.lesgevers:
        status.text = f"{len(state.lesgevers)} lesgevers geladen."


async def _handle_upload(e: events.UploadEventArguments, container: ui.column, status: ui.label):
    try:
        data = await e.file.read()
        state.save_uploaded_file(LESGEVERS_XLSX_PATH, data)
        state.load_lesgevers(LESGEVERS_XLSX_PATH)
        _render_grid(container)
        status.text = f"{len(state.lesgevers)} lesgevers geladen."
        status.classes(remove="text-negative", add="text-positive")
        ui.notify(f"{len(state.lesgevers)} lesgevers geïmporteerd", type="positive")
    except Exception as ex:
        status.text = f"Fout: {ex}"
        status.classes(remove="text-positive", add="text-negative")
        ui.notify(str(ex), type="negative")


def _reload_from_disk(container: ui.column, status: ui.label):
    try:
        state.load_lesgevers(LESGEVERS_XLSX_PATH)
        _render_grid(container)
        status.text = f"{len(state.lesgevers)} lesgevers herladen."
        status.classes(remove="text-negative", add="text-positive")
    except Exception as ex:
        status.text = f"Fout: {ex}"
        status.classes(remove="text-positive", add="text-negative")


def _render_grid(container: ui.column):
    container.clear()
    if not state.lesgevers:
        with container:
            ui.label("Geen lesgevers geladen.").classes("text-grey-6")
        return

    rows = [
        {"naam": lg.naam, "ervaring_jaren": lg.ervaring_jaren, "actief": lg.actief}
        for lg in state.lesgevers
    ]

    col_defs = [
        {"headerName": "Naam", "field": "naam", "editable": True, "width": 250},
        {"headerName": "Ervaring (jaren)", "field": "ervaring_jaren", "editable": True, "width": 150},
        {
            "headerName": "Actief",
            "field": "actief",
            "editable": True,
            "width": 120,
            "cellEditor": "agSelectCellEditor",
            "cellEditorParams": {"values": [True, False]},
        },
    ]

    with container:
        grid = ui.aggrid(
            {
                "columnDefs": col_defs,
                "rowData": rows,
                "defaultColDef": {"sortable": True, "filter": True, "resizable": True},
            }
        ).classes("w-full").style("height: 600px;")
        grid.on("cellValueChanged", lambda e: _on_cell_edit(e, grid))

        with ui.row().classes("q-mt-sm q-gutter-sm"):
            ui.button("Lesgever toevoegen", icon="add", on_click=lambda: _add_row(grid)).props("outline")


def _on_cell_edit(e, grid):
    """Sync AG Grid edits back to state.lesgevers."""
    if not state.lesgevers:
        return
    row_index = e.args["rowIndex"]
    field = e.args["colId"]
    new_value = e.args["value"]

    if 0 <= row_index < len(state.lesgevers):
        lg = state.lesgevers[row_index]
        if field == "naam":
            lg.naam = str(new_value)
        elif field == "ervaring_jaren":
            lg.ervaring_jaren = int(new_value)
        elif field == "actief":
            lg.actief = new_value if isinstance(new_value, bool) else str(new_value).lower() == "true"


async def _add_row(grid):
    new_lg = Lesgever(naam="Nieuw", ervaring_jaren=0, actief=True)
    if state.lesgevers is None:
        state.lesgevers = []
    state.lesgevers.append(new_lg)
    await grid.run_grid_method("applyTransaction", {"add": [{"naam": new_lg.naam, "ervaring_jaren": 0, "actief": True}]})
