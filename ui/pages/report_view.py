"""Report display with auto-refresh on schedule changes."""
from nicegui import ui

from ui.state import state


_report_display: ui.code | None = None
_callback_registered = False


def create_report_tab():
    global _report_display, _callback_registered

    ui.label("Rapport").classes("text-h6 q-mb-sm")

    with ui.row().classes("q-gutter-sm q-mb-md"):
        ui.button("Genereer rapport", icon="assessment", on_click=_refresh).props("color=primary")

    _report_display = ui.code("Nog geen rapport gegenereerd. Laad eerst de planning, lesgevers en datumprikker.").props(
        'language="text"'
    ).classes("w-full").style("white-space: pre-wrap; font-size: 13px; max-height: 80vh; overflow-y: auto;")

    # Register once: auto-refresh whenever state changes (scheduler run, manual edits, etc.)
    if not _callback_registered:
        state.on_change(_refresh)
        _callback_registered = True

    if state.planning and state.datumprikker:
        _refresh()


def _refresh():
    global _report_display
    try:
        text = state.refresh_report()
        if not text:
            text = "Rapport kan niet worden gegenereerd. Controleer of planning, lesgevers en datumprikker geladen zijn."
        if _report_display:
            _report_display.content = text
    except Exception as e:
        if _report_display:
            _report_display.content = f"Fout bij genereren rapport: {e}"
