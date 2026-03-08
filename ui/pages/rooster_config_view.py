"""Form editor for RoosterConfig parameters."""
import yaml
from nicegui import ui

from ui.state import state, ROOSTER_CONFIG_PATH


def create_rooster_config_tab():
    ui.label("Rooster Configuratie").classes("text-h6 q-mb-sm")
    ui.label("Pas de parameters aan waarmee het rooster wordt geoptimaliseerd.").classes(
        "text-caption text-grey-7 q-mb-md"
    )

    cfg = state.rooster_config

    fields: dict[str, ui.number] = {}

    with ui.grid(columns=2).classes("w-full max-w-lg q-gutter-y-sm"):
        fields["lesgever_minimum"] = ui.number(
            "Minimum lesgevers per les", value=cfg.lesgever_minimum, min=0, max=10, step=1
        ).props("outlined dense")
        fields["lesgever_maximum"] = ui.number(
            "Maximum lesgevers per les", value=cfg.lesgever_maximum, min=1, max=10, step=1
        ).props("outlined dense")

        fields["penalty_lesgever_tekort"] = ui.number(
            "Penalty: lesgever tekort", value=cfg.penalty_lesgever_tekort, min=0, step=1
        ).props("outlined dense")
        fields["penalty_misschien"] = ui.number(
            "Penalty: Misschien", value=cfg.penalty_misschien, min=0, step=1
        ).props("outlined dense")

        fields["penalty_geen_ervaren_lesgever"] = ui.number(
            "Penalty: geen ervaren lesgever", value=cfg.penalty_geen_ervaren_lesgever, min=0, step=1
        ).props("outlined dense")
        fields["penalty_meerdere_lessen_per_week"] = ui.number(
            "Penalty: meerdere lessen/week", value=cfg.penalty_meerdere_lessen_per_week, min=0, step=1
        ).props("outlined dense")

        fields["richtlijn_lessen_per_week"] = ui.number(
            "Richtlijn lessen per week", value=cfg.richtlijn_lessen_per_week, min=0, max=5, step=0.1, format="%.2f"
        ).props("outlined dense")
        fields["penalty_boven_richtlijn"] = ui.number(
            "Penalty: boven richtlijn", value=cfg.penalty_boven_richtlijn, min=0, step=1
        ).props("outlined dense")

        fields["penalty_onder_richtlijn"] = ui.number(
            "Penalty: onder richtlijn", value=cfg.penalty_onder_richtlijn, min=0, step=1
        ).props("outlined dense")
        fields["lesgever_bonus"] = ui.number(
            "Bonus: extra lesgever", value=cfg.lesgever_bonus, min=0, step=1
        ).props("outlined dense")

    status = ui.label("").classes("text-caption q-mt-sm")

    with ui.row().classes("q-mt-md q-gutter-sm"):
        ui.button("Toepassen", icon="check", on_click=lambda: _apply(fields, status)).props("color=primary")
        ui.button("Opslaan naar bestand", icon="save", on_click=lambda: _save(fields, status)).props("color=secondary outline")
        ui.button("Herladen", icon="refresh", on_click=lambda: _reload(fields, status)).props("flat")


def _apply(fields: dict[str, ui.number], status: ui.label):
    try:
        _sync_fields_to_config(fields)
        status.text = "Configuratie toegepast."
        status.classes(remove="text-negative", add="text-positive")
        ui.notify("Rooster config toegepast", type="positive")
    except Exception as e:
        status.text = f"Fout: {e}"
        status.classes(remove="text-positive", add="text-negative")


def _save(fields: dict[str, ui.number], status: ui.label):
    try:
        _sync_fields_to_config(fields)
        state.save_rooster_config()
        status.text = f"Opgeslagen naar {ROOSTER_CONFIG_PATH}"
        status.classes(remove="text-negative", add="text-positive")
        ui.notify("Config opgeslagen", type="positive")
    except Exception as e:
        status.text = f"Fout bij opslaan: {e}"
        status.classes(remove="text-positive", add="text-negative")


def _reload(fields: dict[str, ui.number], status: ui.label):
    try:
        from src.config import RoosterConfig
        if ROOSTER_CONFIG_PATH.exists():
            state.rooster_config = RoosterConfig.from_yaml_file(ROOSTER_CONFIG_PATH)
            cfg = state.rooster_config
            for name, field in fields.items():
                field.value = getattr(cfg, name)
            status.text = "Configuratie herladen van bestand."
            status.classes(remove="text-negative", add="text-positive")
        else:
            status.text = "Bestand niet gevonden."
            status.classes(remove="text-positive", add="text-negative")
    except Exception as e:
        status.text = f"Fout: {e}"
        status.classes(remove="text-positive", add="text-negative")


def _sync_fields_to_config(fields: dict[str, ui.number]):
    cfg = state.rooster_config
    for name, field in fields.items():
        val = field.value
        current = getattr(cfg, name)
        if isinstance(current, int):
            setattr(cfg, name, int(val))
        else:
            setattr(cfg, name, float(val))
