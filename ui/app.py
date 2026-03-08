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
        .week-boundary { border-top: 2px solid #7a9cc4 !important; }
    </style>
    """)

    with ui.header().classes("items-center justify-between bg-primary"):
        ui.label("Lesgeef Planner").classes("text-h5 text-white q-ml-md")
        with ui.row().classes("items-center q-gutter-xs"):
            ui.button(icon="menu", on_click=_toggle_left).props("flat color=white dense").tooltip("Verberg/toon linker paneel")
            ui.button(icon="assessment", on_click=_toggle_right).props("flat color=white dense").tooltip("Verberg/toon rapport")
            ui.button("Exporteer Excel", icon="download", on_click=_export).props("flat color=white")

    with ui.element("div").classes("w-full no-wrap").style(
        "display: flex; height: calc(100vh - 80px); overflow: hidden;"
    ):
        # --- Left panel: config & data input ---
        with ui.element("div").props('id="left-panel"').style(
            "width: 350px; min-width: 300px; height: 100%; overflow-y: auto; "
            "border-right: 1px solid #e0e0e0; padding: 8px; flex-shrink: 0;"
        ):
            with ui.tabs().props("dense no-caps").classes("w-full") as left_tabs:
                yaml_tab = ui.tab("YAML", icon="edit_note")
                lesgevers_tab = ui.tab("Lesgevers", icon="people")
                rooster_cfg_tab = ui.tab("Config", icon="tune")

            with ui.tab_panels(left_tabs, value=yaml_tab, on_change=_fix_ag_grid_visibility).classes("w-full"):
                with ui.tab_panel(yaml_tab):
                    create_yaml_editor_tab()
                with ui.tab_panel(lesgevers_tab):
                    create_lesgevers_tab()
                with ui.tab_panel(rooster_cfg_tab):
                    create_rooster_config_tab()

        # --- Center panel: main schedule & availability ---
        with ui.element("div").style(
            "flex: 1; height: 100%; overflow-y: auto; padding: 8px; min-width: 0;"
        ):
            with ui.tabs().classes("w-full") as center_tabs:
                planning_tab = ui.tab("Rooster", icon="calendar_month")
                datumprikker_tab = ui.tab("Beschikbaarheid", icon="event_available")

            with ui.tab_panels(center_tabs, value=planning_tab, on_change=_fix_ag_grid_visibility).classes("w-full"):
                with ui.tab_panel(planning_tab):
                    create_planning_tab()
                with ui.tab_panel(datumprikker_tab):
                    create_datumprikker_tab()

        # --- Right panel: rapport ---
        with ui.element("div").props('id="right-panel"').style(
            "width: 400px; min-width: 320px; height: 100%; overflow-y: auto; "
            "border-left: 1px solid #e0e0e0; padding: 8px; flex-shrink: 0;"
        ):
            create_report_tab()

    ui.timer(0.5, lambda: ui.run_javascript(_AG_GRID_FIX_JS), once=True)


_AG_GRID_FIX_JS = """
document.querySelectorAll('.ag-delay-render').forEach(el => el.classList.remove('ag-delay-render'));
"""


def _fix_ag_grid_visibility():
    ui.run_javascript(_AG_GRID_FIX_JS)


_TOGGLE_PANEL_JS = """
var p=document.getElementById('{id}');
p.style.display = p.style.display==='none' ? '' : 'none';
"""


def _toggle_left():
    ui.run_javascript(_TOGGLE_PANEL_JS.format(id="left-panel"))
    # Give the DOM a moment to reflow, then fix AG Grid visibility
    ui.timer(0.1, _fix_ag_grid_visibility, once=True)


def _toggle_right():
    ui.run_javascript(_TOGGLE_PANEL_JS.format(id="right-panel"))
    ui.timer(0.1, _fix_ag_grid_visibility, once=True)


async def _export():
    try:
        path = state.export()
        ui.notify(f"Planning geëxporteerd naar {path}", type="positive")
    except Exception as e:
        ui.notify(str(e), type="negative")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Lesgeef Planner", port=8080, reload=True)
