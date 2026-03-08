"""Schedule view with AG Grid: dropdown editing, Misschien highlighting, auto-fill."""
from __future__ import annotations

from nicegui import ui

from src.models import Lesgever, Les
from src.report import vind_beschikaarheid
from ui.state import state


LESGEVER_COLS = 3


def create_planning_tab():
    ui.label("Rooster").classes("text-h6 q-mb-sm")

    status = ui.label("").classes("text-caption q-mt-xs q-mb-sm")
    grid_container = ui.column().classes("w-full")

    with ui.row().classes("q-gutter-sm q-mb-md items-center"):
        ui.button(
            "Auto-fill (scheduler)",
            icon="auto_fix_high",
            on_click=lambda: _run_scheduler(grid_container, status),
        ).props("color=primary")
        ui.button(
            "Ververs tabel",
            icon="refresh",
            on_click=lambda: _refresh(grid_container, status),
        ).props("flat")

    _render_grid(grid_container, status)


def _run_scheduler(container: ui.column, status: ui.label):
    try:
        state.run_scheduler()
        state.refresh_report()
        _render_grid(container, status)
        status.text = "Scheduler voltooid. Rapport is bijgewerkt."
        status.classes(remove="text-negative", add="text-positive")
        ui.notify("Rooster automatisch ingevuld", type="positive")
    except Exception as e:
        status.text = f"Fout: {e}"
        status.classes(remove="text-positive", add="text-negative")
        ui.notify(str(e), type="negative")


def _refresh(container: ui.column, status: ui.label):
    _render_grid(container, status)
    status.text = "Tabel ververst."


def _render_grid(container: ui.column, status: ui.label):
    container.clear()
    if state.planning is None:
        with container:
            ui.label("Geen planning geladen. Ga naar 'Planning YAML' om te beginnen.").classes("text-grey-6")
        return

    rows, col_defs = _build_grid_data()

    with container:
        grid = ui.aggrid({
            "columnDefs": col_defs,
            "rowData": rows,
            "defaultColDef": {"sortable": True, "resizable": True},
            ":getRowStyle": """params => {
                if (params.data && params.data._gaat_door === false) {
                    return {opacity: '0.5', fontStyle: 'italic', background: '#f5f5f5'};
                }
            }""",
        }).classes("w-full").style("height: 700px;")
        grid.on("cellValueChanged", lambda e: _on_cell_edit(e, grid, container, status))


def _build_grid_data() -> tuple[list[dict], list[dict]]:
    """Build AG Grid row data and column definitions from the current planning."""
    planning = state.planning
    dp = state.datumprikker

    col_defs: list[dict] = [
        {"headerName": "Seizoen", "field": "seizoen", "width": 120},
        {"headerName": "Datum", "field": "datum", "width": 130},
        {"headerName": "Tijd", "field": "tijd", "width": 120},
    ]

    has_dp = dp is not None

    for i in range(LESGEVER_COLS):
        col_def: dict = {
            "headerName": f"Lesgever {i + 1}",
            "field": f"lesgever_{i}",
            "width": 140,
            "cellClassRules": {
                "misschien-cell": f"data && data['_misschien_{i}'] === true",
            },
        }
        if has_dp:
            col_def["editable"] = True
            col_def["cellEditor"] = "agSelectCellEditor"
            col_def["cellEditorParams"] = {"values": [""]}
        col_defs.append(col_def)

    col_defs.append({"headerName": "Info", "field": "info", "width": 200})

    rows: list[dict] = []
    for idx, les in enumerate(planning.lessen):
        row: dict = {
            "_idx": idx,
            "_gaat_door": les.gaat_door,
            "seizoen": les.seizoen.naam if les.seizoen else "",
            "datum": les.datum.strftime("%a %d/%m/%Y"),
            "tijd": les.tijd,
            "info": les.naam or ("Geen les" if not les.gaat_door else ""),
        }

        for i in range(LESGEVER_COLS):
            naam = ""
            is_misschien = False
            if les.lesgevers and i < len(les.lesgevers):
                naam = les.lesgevers[i].naam
                if dp:
                    b = vind_beschikaarheid(dp, les.lesgevers[i], les)
                    is_misschien = b == "Misschien"
            row[f"lesgever_{i}"] = naam
            row[f"_misschien_{i}"] = is_misschien

        rows.append(row)

    if has_dp:
        all_names: set[str] = {""}
        for lg in dp.lesgevers_al_ingevuld:
            all_names.add(lg.naam)
        for col_def in col_defs:
            if col_def.get("field", "").startswith("lesgever_"):
                col_def["cellEditorParams"] = {"values": sorted(all_names)}

    return rows, col_defs


def _get_dropdown_values(les: Les) -> list[str]:
    """Get sorted dropdown options: Ja first, then Misschien."""
    available = state.get_available_lesgevers_for_lesson(les)
    names = [""] + [lg.naam for lg, _ in available]
    return names


def _on_cell_edit(e, grid, container: ui.column, status: ui.label):
    """Handle inline cell edits: update the Les model and refresh report."""
    args = e.args
    row_idx = args.get("rowIndex")
    field = args.get("colId", "")
    new_value = args.get("value", "")

    if not field.startswith("lesgever_") or state.planning is None:
        return

    col_i = int(field.split("_")[1])
    les = state.planning.lessen[row_idx]

    if les.lesgevers is None:
        les.lesgevers = []

    _update_lesgever_assignment(les, col_i, new_value)

    state.refresh_report()
    _render_grid(container, status)


def _update_lesgever_assignment(les: Les, col_index: int, name: str):
    """Set or clear a lesgever assignment at the given column index."""
    if les.lesgevers is None:
        les.lesgevers = []

    lesgever = _find_lesgever_by_name(name) if name else None

    while len(les.lesgevers) <= col_index:
        les.lesgevers.append(None)  # type: ignore[arg-type]

    if lesgever:
        les.lesgevers[col_index] = lesgever
    else:
        if col_index < len(les.lesgevers):
            les.lesgevers[col_index] = None  # type: ignore[assignment]

    les.lesgevers = [lg for lg in les.lesgevers if lg is not None]


def _find_lesgever_by_name(name: str) -> Lesgever | None:
    if state.datumprikker:
        for lg in state.datumprikker.lesgevers_al_ingevuld:
            if lg.naam == name:
                return lg
    if state.lesgevers:
        for lg in state.lesgevers:
            if lg.naam == name:
                return lg
    return None
