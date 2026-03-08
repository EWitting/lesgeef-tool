"""Schedule view with AG Grid: dropdown editing, Misschien highlighting, auto-fill."""
from __future__ import annotations

import asyncio
from nicegui import ui

from src.models import Lesgever, Les
from src.report import vind_beschikaarheid
from ui.state import state


LESGEVER_COLS = 3
_AG_FIX_JS = "document.querySelectorAll('.ag-delay-render').forEach(el => el.classList.remove('ag-delay-render'));"

# Held across calls so we can do in-place data updates without grid recreation
_grid_ref: ui.aggrid | None = None
_last_has_dp: bool | None = None  # track whether datumprikker was loaded when grid was built


def create_planning_tab():
    status = ui.label("").classes("text-caption q-mb-xs").style("min-height: 0;")
    status.set_visibility(False)
    grid_container = ui.column().classes("w-full")

    with ui.row().classes("q-gutter-sm q-mb-sm items-center"):
        run_btn = ui.button(
            "Auto-fill",
            icon="auto_fix_high",
            on_click=lambda: _run_scheduler(grid_container, status, run_btn),
        ).props("color=primary dense")
        ui.button(
            "Ververs",
            icon="refresh",
            on_click=lambda: _rebuild_grid(grid_container, status),
        ).props("flat dense")

    _rebuild_grid(grid_container, status)


async def _run_scheduler(container: ui.column, status: ui.label, btn: ui.button):
    btn.props("loading")
    status.text = "Scheduler bezig..."
    try:
        # Run OR-Tools in a thread so the event loop stays responsive
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, state.run_scheduler)
        await _update_grid_data(container, status)
        state._notify()
        status.set_text("Scheduler voltooid.")
        status.classes(remove="text-negative", add="text-positive")
        status.set_visibility(True)
        ui.notify("Rooster automatisch ingevuld", type="positive")
    except Exception as e:
        status.set_text(f"Fout: {e}")
        status.classes(remove="text-positive", add="text-negative")
        status.set_visibility(True)
        ui.notify(str(e), type="negative")
    finally:
        btn.props(remove="loading")


def _rebuild_grid(container: ui.column, status: ui.label):
    """Fully recreate the grid (needed when column defs change, e.g. after loading datumprikker)."""
    global _grid_ref, _last_has_dp
    container.clear()
    _grid_ref = None

    if state.planning is None:
        with container:
            ui.label("Geen planning geladen. Ga naar 'Planning YAML' om te beginnen.").classes("text-grey-6")
        return

    rows, col_defs, availability_js = _build_grid_data()
    has_dp = state.datumprikker is not None
    _last_has_dp = has_dp

    with container:
        _grid_ref = ui.aggrid({
            "columnDefs": col_defs,
            "rowData": rows,
            "defaultColDef": {"sortable": True, "resizable": True},
            ":isFullWidthRow": "params => !!(params.rowNode.data && params.rowNode.data._is_season_header)",
            ":fullWidthCellRenderer": """params => {
                const div = document.createElement('div');
                div.style.cssText = 'background: #2c5282; color: white; font-weight: bold; font-size: 13px; padding: 0 16px; display: flex; align-items: center; height: 100%; letter-spacing: 0.05em;';
                div.textContent = params.data._season_name || '';
                return div;
            }""",
            ":getRowStyle": """params => {
                if (!params.data || params.data._is_season_header) return;
                var even = params.data._week % 2 === 0;
                if (params.data._gaat_door === false) {
                    return {fontStyle: 'italic', color: '#999', background: even ? '#d0d8e8' : '#e4e4e4'};
                }
                return {background: even ? '#dce6f1' : '#f0f0f0'};
            }""",
        }).classes("w-full").style("height: 700px;")
        _grid_ref.on("cellValueChanged", lambda e: _on_cell_edit(e, container, status))

    ui.run_javascript(f"window._lesgeefAvail = {availability_js};")
    ui.run_javascript(_AG_FIX_JS)


async def _update_grid_data(container: ui.column, status: ui.label):
    """Update row data in-place if the grid already exists; rebuild if column defs changed."""
    global _grid_ref, _last_has_dp
    has_dp = state.datumprikker is not None

    if _grid_ref is None or _last_has_dp != has_dp:
        # Column defs changed (datumprikker loaded/unloaded) — full rebuild needed
        _rebuild_grid(container, status)
        return

    rows, _col_defs, availability_js = _build_grid_data()
    # Update row data without destroying the grid element
    await _grid_ref.run_grid_method("setGridOption", "rowData", rows)
    ui.run_javascript(f"window._lesgeefAvail = {availability_js};")
    ui.run_javascript(_AG_FIX_JS)


def _build_grid_data() -> tuple[list[dict], list[dict], str]:
    """Build AG Grid row data, column definitions, and per-row availability JS from current planning."""
    import json
    planning = state.planning
    dp = state.datumprikker
    has_dp = dp is not None

    boundary = {"week-boundary": "data && data['_new_week'] === true"}

    col_defs: list[dict] = [
        {"headerName": "Datum", "field": "datum", "width": 130, "cellClassRules": boundary},
        {"headerName": "Tijd", "field": "tijd", "width": 120, "cellClassRules": boundary},
    ]

    for i in range(LESGEVER_COLS):
        col_def: dict = {
            "headerName": f"Lesgever {i + 1}",
            "field": f"lesgever_{i}",
            "width": 150,
            "cellClassRules": {
                "misschien-cell": f"data && data['_misschien_{i}'] === true",
                "week-boundary": "data && data['_new_week'] === true",
            },
        }
        if has_dp:
            col_def["editable"] = True
            col_def["cellEditor"] = "agSelectCellEditor"
            # `:` prefix = evaluated as JS function on client; reads per-row availability
            # from the window._lesgeefAvail global we inject after grid creation.
            col_def[":cellEditorParams"] = (
                "params => { "
                "  var idx = params.data._idx; "
                "  var avail = (window._lesgeefAvail && window._lesgeefAvail[idx]) || ['']; "
                "  return { values: avail }; "
                "}"
            )
        col_defs.append(col_def)

    col_defs.append({"headerName": "Info", "field": "info", "width": 200, "cellClassRules": boundary})

    # Build per-row availability lookup: {lesson_idx: ["", "Alice", "⚠ Bob", ...]}
    # "" = unassign, plain names = Ja, "⚠ name" = Misschien
    availability: dict[int, list[str]] = {}
    rows: list[dict] = []
    prev_week: int | None = None
    prev_seizoen: str | None = None

    for idx, les in enumerate(planning.lessen):
        week = les.datum.isocalendar()[1]
        seizoen_naam = les.seizoen.naam if les.seizoen else ""

        # Insert a full-width season header row when the season changes
        if seizoen_naam and seizoen_naam != prev_seizoen:
            rows.append({"_is_season_header": True, "_season_name": seizoen_naam})
            prev_seizoen = seizoen_naam
            prev_week = None  # reset so first week of new season also gets a boundary line

        row: dict = {
            "_idx": idx,
            "_is_season_header": False,
            "_gaat_door": les.gaat_door,
            "_week": week,
            "_new_week": week != prev_week,
            "seizoen": seizoen_naam,
            "datum": les.datum.strftime("%a %d/%m/%Y"),
            "tijd": les.tijd,
            "info": les.naam or ("Geen les" if not les.gaat_door else ""),
        }
        prev_week = week

        for i in range(LESGEVER_COLS):
            naam = ""
            is_misschien = False
            if les.lesgevers and i < len(les.lesgevers):
                assigned = les.lesgevers[i]
                naam = assigned.naam
                if dp:
                    b = vind_beschikaarheid(dp, assigned, les)
                    is_misschien = b == "Misschien"
            row[f"lesgever_{i}"] = naam
            row[f"_misschien_{i}"] = is_misschien

        if has_dp:
            avail_for_les = state.get_available_lesgevers_for_lesson(les)
            options: list[str] = [""]
            for lg, b in avail_for_les:
                options.append(f"⚠ {lg.naam}" if b == "Misschien" else lg.naam)
            availability[idx] = options

        rows.append(row)

    availability_js = json.dumps(availability)
    return rows, col_defs, availability_js



async def _on_cell_edit(e, container: ui.column, status: ui.label):
    """Handle inline cell edits: update the Les model and refresh report."""
    args = e.args
    field = args.get("colId", "")
    new_value = args.get("value", "")
    row_data = args.get("data", {})

    if not field.startswith("lesgever_") or state.planning is None:
        return
    if row_data.get("_is_season_header"):
        return

    # Use _idx from row data -- robust against inserted season header rows
    les_idx = row_data.get("_idx")
    if les_idx is None:
        return

    # Strip the ⚠ prefix used to indicate Misschien in the dropdown
    clean_value = str(new_value).removeprefix("⚠ ") if new_value else ""

    col_i = int(field.split("_")[1])
    les = state.planning.lessen[les_idx]

    if les.lesgevers is None:
        les.lesgevers = []

    _update_lesgever_assignment(les, col_i, clean_value)

    state._notify()  # triggers report_view auto-refresh via on_change callback
    await _update_grid_data(container, status)


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
