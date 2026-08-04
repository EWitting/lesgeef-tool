"""NiceGUI-app entrypoint. Wordt in fase 2 uitgebreid met de volledige lay-out."""
from nicegui import ui


@ui.page("/")
def index() -> None:
    ui.label("Lesgeefplanner").classes("text-h5")
