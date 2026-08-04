"""Het middenpaneel: de planning, altijd zichtbaar. Zie docs/DESIGN.md §4.7 en §2.6.

Ververst per rij (`refresh_les`) in plaats van de hele lijst opnieuw op te bouwen
(`rebuild`), zodat een enkele bewerking niet de hele DOM-boom opnieuw hoeft te tekenen --
dat was precies het probleem met de oude AG Grid-integratie."""
from __future__ import annotations

from nicegui import ui

from ..domain.formatting import format_datum, format_tijdvak
from ..model.entities import Les
from ..model.project import Project
from .state import state

_WEEK_GRENS_STIJL = "border-top: 2px solid #7a9cc4;"
_GEEN_WEEK_GRENS_STIJL = "border-top: 1px solid transparent;"
_EVEN_WEEK_KLEUR = "#dce6f1"
_ONEVEN_WEEK_KLEUR = "#f0f0f0"


class LessonRow:
    """Eén rij, één keer opgebouwd. `ververs()` past alleen de teksten/klassen aan."""

    def __init__(self, container: ui.column, les: Les, project: Project, nieuwe_week: bool) -> None:
        with container:
            with ui.row().classes("items-center q-px-sm").style(
                "flex-wrap: nowrap; min-height: 32px;"
                + (_WEEK_GRENS_STIJL if nieuwe_week else _GEEN_WEEK_GRENS_STIJL)
            ) as self.root:
                self.stip = ui.icon("circle").classes("text-transparent").style(
                    "font-size: 9px; width: 12px;"
                )
                self.datum_label = ui.label().classes("text-caption").style("width: 110px;")
                self.tijd_label = ui.label().classes("text-caption").style("width: 95px;")
                self.titel_label = ui.label().classes("text-caption").style(
                    "width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                )
                self.slots_container = ui.row().classes("items-center").style(
                    "flex-wrap: nowrap; gap: 4px;"
                )
                self.slots: list[ui.label] = []

        self.ververs(les, project)

    def ververs(self, les: Les, project: Project) -> None:
        even_week = les.datum.isocalendar()[1] % 2 == 0
        achtergrond = _EVEN_WEEK_KLEUR if even_week else _ONEVEN_WEEK_KLEUR
        vervallen = les.status == "vervallen"
        self.root.style(replace=f"background: {achtergrond}; flex-wrap: nowrap; min-height: 32px;")
        if vervallen:
            self.root.classes(add="text-grey text-italic")
        else:
            self.root.classes(remove="text-grey text-italic")

        self.datum_label.set_text(format_datum(les.datum))
        self.tijd_label.set_text(format_tijdvak(les.begin_tijd, les.eind_tijd))

        if vervallen:
            titel = "Vervalt" + (f" — {les.vervallen_reden}" if les.vervallen_reden else "")
        else:
            titel = les.titel or ""
        self.titel_label.set_text(titel)

        namen = {lg.id: lg.naam for lg in project.lesgevers}
        aantal_slots = max(project.solver_config.lesgever_maximum, len(les.toewijzingen))
        while len(self.slots) < aantal_slots:
            with self.slots_container:
                self.slots.append(
                    ui.label().classes("text-caption").style("width: 120px;")
                )
        for i, slot in enumerate(self.slots):
            slot.set_visibility(i < aantal_slots)
            if vervallen:
                slot.set_text("")
            elif i < len(les.toewijzingen):
                tw = les.toewijzingen[i]
                naam = namen.get(tw.lesgever_id, "? (onbekend)")
                slot.set_text(f"\U0001F4CC {naam}" if tw.vast else naam)
            else:
                slot.set_text("—")


class PlanningView:
    def __init__(self, container: ui.column) -> None:
        self._container = container
        self._rows: dict[str, LessonRow] = {}

    def rebuild(self) -> None:
        self._container.clear()
        self._rows.clear()

        if state.doc is None:
            with self._container:
                ui.label("Geen project geopend. Ga naar het startscherm om te beginnen.").classes(
                    "text-grey-6 q-pa-md"
                )
            return

        project = state.doc.project
        lessen = sorted(project.lessen, key=lambda l: (l.datum, l.begin_tijd))

        if not lessen:
            with self._container:
                ui.label(
                    "Nog geen lessen. Stel eerst seizoenen en een weekrooster in."
                ).classes("text-grey-6 q-pa-md")
            return

        seizoen_naam = {s.id: s.naam for s in project.seizoenen}

        vorige_seizoen_id: object = object()
        vorige_week: int | None = None

        with self._container:
            for les in lessen:
                seizoen_id = les.herkomst.seizoen_id if les.herkomst else les.seizoen_id
                if seizoen_id != vorige_seizoen_id:
                    naam = seizoen_naam.get(seizoen_id, "Overig")
                    ui.label(naam).classes(
                        "text-subtitle2 text-weight-bold text-white q-px-sm"
                    ).style("background: #2c5282; width: 100%; padding-top: 4px; padding-bottom: 4px;")
                    vorige_seizoen_id = seizoen_id
                    vorige_week = None

                week = les.datum.isocalendar()[1]
                nieuwe_week = week != vorige_week
                vorige_week = week

                rij = LessonRow(self._container, les, project, nieuwe_week)
                self._rows[les.id] = rij

    def refresh_les(self, les_id: str) -> None:
        if state.doc is None:
            return
        rij = self._rows.get(les_id)
        if rij is None:
            self.rebuild()
            return
        project = state.doc.project
        les = next((l for l in project.lessen if l.id == les_id), None)
        if les is None:
            self.rebuild()
            return
        rij.ververs(les, project)

    def refresh_lessen(self, les_ids) -> None:
        for les_id in les_ids:
            self.refresh_les(les_id)
