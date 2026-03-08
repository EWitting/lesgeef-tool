"""Upload and view datumprikker availability matrix."""
from nicegui import events, ui

from ui.state import state


def create_datumprikker_tab():
    ui.label("Beschikbaarheid (Datumprikker)").classes("text-h6 q-mb-sm")
    ui.label(
        "Upload de Google Forms export (.xlsx). Planning en lesgevers moeten eerst geladen zijn."
    ).classes("text-caption text-grey-7 q-mb-sm")

    status = ui.label("").classes("text-caption q-mt-xs q-mb-sm")

    ui.upload(
        label="Upload datumprikker .xlsx",
        auto_upload=True,
        on_upload=lambda e: _handle_upload(e, grid_container, status),
    ).props('accept=".xlsx,.xls" flat bordered').classes("max-w-xs q-mb-md")

    grid_container = ui.column().classes("w-full")
    _render_grid(grid_container, status)


async def _handle_upload(e: events.UploadEventArguments, container: ui.column, status: ui.label):
    try:
        import tempfile, os
        data = await e.file.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(data)
        tmp.close()
        state.load_datumprikker(tmp.name)
        os.unlink(tmp.name)
        _render_grid(container, status)
        n_lg = len(state.datumprikker.lesgevers_al_ingevuld)
        n_les = len(state.datumprikker.lessen)
        status.text = f"Datumprikker geladen: {n_lg} lesgevers, {n_les} lessen."
        status.classes(remove="text-negative", add="text-positive")
        ui.notify(f"Datumprikker geladen ({n_lg} lesgevers, {n_les} lessen)", type="positive")
    except Exception as ex:
        status.text = f"Fout: {ex}"
        status.classes(remove="text-positive", add="text-negative")
        ui.notify(str(ex), type="negative")


def _render_grid(container: ui.column, status: ui.label):
    container.clear()
    dp = state.datumprikker
    if dp is None:
        with container:
            ui.label("Geen datumprikker geladen.").classes("text-grey-6")
        return

    status.text = f"{len(dp.lesgevers_al_ingevuld)} lesgevers ingevuld, {len(dp.lesgevers_nog_te_vullen)} nog te vullen."

    les_labels = [f"{les.datum.strftime('%a %d/%m')} {les.tijd}" for les in dp.lessen]

    col_defs: list[dict] = [
        {"headerName": "Lesgever", "field": "naam", "pinned": "left", "width": 140},
    ]
    for i, label in enumerate(les_labels):
        col_defs.append({
            "headerName": label,
            "field": f"les_{i}",
            "width": 120,
            "cellClassRules": {
                "bg-green-2 text-green-9": f'x === "Ja"',
                "bg-orange-2 text-orange-9": f'x === "Misschien"',
                "bg-red-1 text-red-9": f'x === "Nee"',
            },
        })

    rows = []
    for lg_idx, lg in enumerate(dp.lesgevers_al_ingevuld):
        row = {"naam": lg.naam}
        for les_idx in range(len(dp.lessen)):
            row[f"les_{les_idx}"] = dp.beschikbaarheid[lg_idx][les_idx]
        rows.append(row)

    with container:
        ui.aggrid({
            "columnDefs": col_defs,
            "rowData": rows,
            "defaultColDef": {"sortable": True, "resizable": True},
        }).classes("w-full").style("height: 600px;")

        if dp.lesgevers_nog_te_vullen:
            with ui.expansion("Nog niet ingevuld", icon="warning").classes("q-mt-md"):
                for lg in dp.lesgevers_nog_te_vullen:
                    ui.label(f"  - {lg.naam}")
