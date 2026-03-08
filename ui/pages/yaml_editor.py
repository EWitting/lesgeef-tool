"""Plain-text YAML editor for planning.yml with parse & apply."""
from nicegui import ui

from ui.state import state, PLANNING_YAML_PATH


def create_yaml_editor_tab():
    initial_text = ""
    if PLANNING_YAML_PATH.exists():
        initial_text = PLANNING_YAML_PATH.read_text(encoding="utf-8")

    ui.label("Planning YAML").classes("text-h6 q-mb-sm")
    ui.label("Bewerk de planning configuratie als YAML. Klik 'Toepassen' om te parsen en de planning te genereren.").classes("text-caption text-grey-7 q-mb-sm")

    editor = ui.textarea(value=initial_text).props(
        'outlined autogrow input-style="font-family: monospace; font-size: 13px; line-height: 1.4"'
    ).classes("w-full").style("min-height: 400px")

    status = ui.label("").classes("text-caption q-mt-sm")

    with ui.row().classes("q-mt-sm q-gutter-sm"):
        ui.button("Toepassen", icon="check", on_click=lambda: _apply(editor, status)).props("color=primary")
        ui.button("Opslaan naar bestand", icon="save", on_click=lambda: _save(editor, status)).props("color=secondary outline")
        ui.button("Herladen van bestand", icon="refresh", on_click=lambda: _reload(editor, status)).props("flat")


def _apply(editor: ui.textarea, status: ui.label):
    try:
        text = editor.value
        state.load_planning_from_yaml_string(text)
        n = len(state.planning.lessen) if state.planning else 0
        status.text = f"Planning succesvol geparsed: {n} lessen gegenereerd."
        status.classes(remove="text-negative", add="text-positive")
        ui.notify(f"Planning geladen: {n} lessen", type="positive")
    except Exception as e:
        status.text = f"Fout: {e}"
        status.classes(remove="text-positive", add="text-negative")
        ui.notify(str(e), type="negative")


def _save(editor: ui.textarea, status: ui.label):
    try:
        state.save_planning_yaml(editor.value)
        status.text = f"Opgeslagen naar {PLANNING_YAML_PATH}"
        status.classes(remove="text-negative", add="text-positive")
        ui.notify("YAML opgeslagen", type="positive")
    except Exception as e:
        status.text = f"Fout bij opslaan: {e}"
        status.classes(remove="text-positive", add="text-negative")


def _reload(editor: ui.textarea, status: ui.label):
    if PLANNING_YAML_PATH.exists():
        editor.value = PLANNING_YAML_PATH.read_text(encoding="utf-8")
        status.text = "Bestand herladen."
        status.classes(remove="text-negative", add="text-positive")
    else:
        status.text = "Bestand niet gevonden."
        status.classes(remove="text-positive", add="text-negative")
