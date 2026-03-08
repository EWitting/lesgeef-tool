"""NiceGUI application entry point with tabbed layout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nicegui import ui

from ui.state import state
from ui.pages.yaml_editor import create_yaml_editor_tab
from ui.pages.lesgevers_view import create_lesgevers_tab
from ui.pages.datumprikker_view import create_datumprikker_tab
from ui.pages.rooster_config_view import create_rooster_config_tab
from ui.pages.planning_view import create_planning_tab
from ui.pages.report_view import create_report_tab


@ui.page("/")
def index():
    ui.add_head_html("""
    <style>
        .ag-theme-quartz { --ag-row-height: 34px; }
        .misschien-cell { background-color: #fff3cd !important; }
        .geen-les-row { opacity: 0.5; font-style: italic; }
    </style>
    """)

    with ui.header().classes("items-center justify-between bg-primary"):
        ui.label("Lesgeef Planner").classes("text-h5 text-white q-ml-md")
        ui.button("Exporteer Excel", icon="download", on_click=_export).props("flat color=white")

    with ui.tabs().classes("w-full") as tabs:
        planning_yaml_tab = ui.tab("Planning YAML", icon="edit_note")
        lesgevers_tab = ui.tab("Lesgevers", icon="people")
        datumprikker_tab = ui.tab("Beschikbaarheid", icon="event_available")
        rooster_cfg_tab = ui.tab("Rooster Config", icon="tune")
        planning_tab = ui.tab("Rooster", icon="calendar_month")
        report_tab = ui.tab("Rapport", icon="assessment")

    with ui.tab_panels(tabs, value=planning_tab, on_change=_fix_ag_grid_visibility).classes("w-full flex-grow"):
        with ui.tab_panel(planning_yaml_tab):
            create_yaml_editor_tab()
        with ui.tab_panel(lesgevers_tab):
            create_lesgevers_tab()
        with ui.tab_panel(datumprikker_tab):
            create_datumprikker_tab()
        with ui.tab_panel(rooster_cfg_tab):
            create_rooster_config_tab()
        with ui.tab_panel(planning_tab):
            create_planning_tab()
        with ui.tab_panel(report_tab):
            create_report_tab()

    # AG Grid uses animation-based visibility detection to remove .ag-delay-render.
    # Inside Quasar tab panels this detection fails, so we strip the class manually.
    ui.timer(0.5, lambda: ui.run_javascript(_AG_GRID_FIX_JS), once=True)


_AG_GRID_FIX_JS = """
document.querySelectorAll('.ag-delay-render').forEach(el => el.classList.remove('ag-delay-render'));
"""


def _fix_ag_grid_visibility():
    ui.run_javascript(_AG_GRID_FIX_JS)


async def _export():
    try:
        path = state.export()
        ui.notify(f"Planning geëxporteerd naar {path}", type="positive")
    except Exception as e:
        ui.notify(str(e), type="negative")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Lesgeef Planner", port=8080, reload=True)
