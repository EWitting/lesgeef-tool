"""Het middenpaneel: de planning, altijd zichtbaar. Zie docs/DESIGN.md §4.7 en §2.6.

Ververst per rij (`refresh_les`) in plaats van de hele lijst opnieuw op te bouwen
(`rebuild`), zodat een enkele bewerking niet de hele DOM-boom opnieuw hoeft te tekenen --
dat was precies het probleem met de oude AG Grid-integratie. Roep `rebuild()` daarom NOOIT
aan na een gewone celwijziging (alleen bij het wisselen van project of scope)."""
from __future__ import annotations

from datetime import date
from typing import Callable

from nicegui import ui

from ..domain.formatting import format_datum, format_datum_lang, format_tijd, format_tijdvak
from ..model.entities import Les
from ..model.project import Project
from . import lesbewerkingen as lb
from .state import state

_WEEK_GRENS_STIJL = "border-top: 2px solid #7a9cc4;"
_GEEN_WEEK_GRENS_STIJL = "border-top: 1px solid transparent;"
_EVEN_WEEK_KLEUR = "#dce6f1"
_ONEVEN_WEEK_KLEUR = "#f0f0f0"
_PIN = "\U0001F4CC"


class LessonRow:
    """Eén rij, één keer opgebouwd. `ververs()` past alleen de teksten/klassen/menu-inhoud
    aan; de knoppen en hun aantal blijven zo veel mogelijk staan."""

    def __init__(
        self,
        container: ui.column,
        les: Les,
        project: Project,
        nieuwe_week: bool,
        on_wijziging: Callable[[str], None],
    ) -> None:
        self._on_wijziging = on_wijziging
        self._les_id = les.id

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
                self.slot_knoppen: list[ui.button] = []
                self.slot_menus: list[ui.menu] = []

                self.acties_btn = ui.button(icon="more_vert").props("flat dense size=sm")
                with self.acties_btn:
                    self.acties_menu = ui.menu()

        self.ververs(les, project)

    # ------------------------------------------------------------------

    def ververs(self, les: Les, project: Project) -> None:
        self._les_id = les.id
        even_week = les.datum.isocalendar()[1] % 2 == 0
        achtergrond = _EVEN_WEEK_KLEUR if even_week else _ONEVEN_WEEK_KLEUR
        vervallen = les.status == "vervallen"
        self.root.style(replace=f"background: {achtergrond}; flex-wrap: nowrap; min-height: 32px;")
        self.root.classes(
            add="text-grey text-italic" if vervallen else "", remove="" if vervallen else "text-grey text-italic"
        )

        self.datum_label.set_text(format_datum(les.datum))
        self.tijd_label.set_text(format_tijdvak(les.begin_tijd, les.eind_tijd))

        if vervallen:
            titel = "Vervalt" + (f" — {les.vervallen_reden}" if les.vervallen_reden else "")
        elif les.soort == "extra":
            titel = les.titel or "Extra les"
        else:
            titel = les.titel or ""
        self.titel_label.set_text(titel)

        aantal_slots = 0 if vervallen else max(
            project.solver_config.lesgever_maximum, len(les.toewijzingen)
        )
        while len(self.slot_knoppen) < aantal_slots:
            i = len(self.slot_knoppen)
            with self.slots_container:
                knop = ui.button().props("flat dense no-caps size=sm").style(
                    "width: 130px; justify-content: flex-start;"
                )
                with knop:
                    menu = ui.menu()
                self.slot_knoppen.append(knop)
                self.slot_menus.append(menu)

        for i, knop in enumerate(self.slot_knoppen):
            knop.set_visibility(i < aantal_slots)
        if not vervallen:
            for i in range(aantal_slots):
                self._ververs_slot(i, les, project)

        self._ververs_acties_menu(les)

    def _ververs_slot(self, i: int, les: Les, project: Project) -> None:
        knop = self.slot_knoppen[i]
        menu = self.slot_menus[i]
        namen = {lg.id: lg.naam for lg in project.lesgevers}

        bezet = i < len(les.toewijzingen)
        if bezet:
            tw = les.toewijzingen[i]
            naam = namen.get(tw.lesgever_id, "? (onbekend)")
            knop.set_text(f"{_PIN} {naam}" if tw.vast else naam)
        else:
            knop.set_text("—")

        menu.clear()
        with menu:
            actieve_lesgevers = sorted(
                (lg for lg in project.lesgevers if lg.actief), key=lambda lg: lg.naam.lower()
            )
            if not actieve_lesgevers:
                ui.menu_item("Geen actieve lesgevers").props("disable")
            for lg in actieve_lesgevers:
                aantal = lb.aantal_lessen_voor(project, lg.id)
                ui.menu_item(
                    f"{lg.naam} ({aantal} {'les' if aantal == 1 else 'lessen'})",
                    on_click=lambda lg_id=lg.id: self._klik_toewijzen(i, lg_id),
                )
            if bezet:
                ui.separator()
                tw = les.toewijzingen[i]
                ui.menu_item(
                    f"{_PIN} Losmaken" if tw.vast else f"{_PIN} Vastzetten",
                    on_click=lambda: self._klik_vast(i),
                )
                ui.menu_item("✕ Wissen", on_click=lambda: self._klik_wissen(i))

    def _ververs_acties_menu(self, les: Les) -> None:
        self.acties_menu.clear()
        vervallen = les.status == "vervallen"
        with self.acties_menu:
            if vervallen:
                ui.menu_item("Gaat weer door", on_click=lambda: self._klik_gaat_weer_door())
            else:
                ui.menu_item("Vervalt…", on_click=lambda: self._klik_vervalt())
            ui.menu_item("Tijd aanpassen…", on_click=lambda: self._klik_tijd_aanpassen(les))
            ui.menu_item("Titel geven…", on_click=lambda: self._klik_titel_geven(les))
            if les.soort == "extra":
                ui.separator()
                ui.menu_item("Verwijderen", on_click=lambda: self._klik_verwijderen())

    # ------------------------------------------------------------------
    # Klikhandlers -- muteren via lesbewerkingen.py, verversen daarna via de callback
    # ------------------------------------------------------------------

    def _klik_toewijzen(self, slot_index: int, lesgever_id: str) -> None:
        gelukt = lb.wijs_lesgever_toe(self._les_id, slot_index, lesgever_id)
        if not gelukt:
            ui.notify("Deze lesgever staat al op deze les.", type="warning")
            return
        self._on_wijziging(self._les_id)

    def _klik_vast(self, slot_index: int) -> None:
        lb.wissel_vast(self._les_id, slot_index)
        self._on_wijziging(self._les_id)

    def _klik_wissen(self, slot_index: int) -> None:
        lb.wis_toewijzing(self._les_id, slot_index)
        self._on_wijziging(self._les_id)

    def _klik_gaat_weer_door(self) -> None:
        lb.markeer_gaat_weer_door(self._les_id)
        self._on_wijziging(self._les_id)

    async def _klik_vervalt(self) -> None:
        with ui.dialog() as dialoog, ui.card():
            ui.label("Les laten vervallen").classes("text-subtitle1")
            reden_veld = ui.input("Reden (bv. 'Beka', 'Lustrum Trip')").classes("full-width")
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
                ui.button(
                    "Vervalt", on_click=lambda: dialoog.submit(reden_veld.value)
                ).props("color=negative")

        reden = await dialoog
        if reden is None:
            return
        lb.markeer_vervallen(self._les_id, reden)
        self._on_wijziging(self._les_id)

    async def _klik_tijd_aanpassen(self, les: Les) -> None:
        with ui.dialog() as dialoog, ui.card():
            ui.label("Tijd aanpassen").classes("text-subtitle1")
            with ui.row():
                begin_veld = ui.input("Begintijd (HH:MM)", value=format_tijd(les.begin_tijd))
                eind_veld = ui.input("Eindtijd (HH:MM)", value=format_tijd(les.eind_tijd))
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
                ui.button(
                    "Opslaan",
                    on_click=lambda: dialoog.submit((begin_veld.value, eind_veld.value)),
                ).props("color=primary")

        resultaat = await dialoog
        if resultaat is None:
            return
        begin_str, eind_str = resultaat
        try:
            from ..domain.formatting import parse_nl_tijd

            begin_tijd = parse_nl_tijd(begin_str)
            eind_tijd = parse_nl_tijd(eind_str)
        except ValueError:
            ui.notify("Ongeldige tijd. Gebruik het formaat HH:MM.", type="negative")
            return
        lb.wijzig_tijd(self._les_id, begin_tijd, eind_tijd)
        self._on_wijziging(self._les_id)

    async def _klik_titel_geven(self, les: Les) -> None:
        with ui.dialog() as dialoog, ui.card():
            ui.label("Titel geven").classes("text-subtitle1")
            titel_veld = ui.input("Titel", value=les.titel or "").classes("full-width")
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
                ui.button(
                    "Opslaan", on_click=lambda: dialoog.submit(titel_veld.value)
                ).props("color=primary")

        titel = await dialoog
        if titel is None:
            return
        lb.wijzig_titel(self._les_id, titel)
        self._on_wijziging(self._les_id)

    def _klik_verwijderen(self) -> None:
        gelukt = lb.verwijder_extra_les(self._les_id)
        if gelukt:
            self._on_wijziging(self._les_id)


class PlanningView:
    def __init__(
        self, container: ui.column, on_wijziging_header: Callable[[], None] | None = None
    ) -> None:
        self._container = container
        self._rows: dict[str, LessonRow] = {}
        # Wordt aangeroepen na elke bewerking, naast het verversen van de rij(en) zelf --
        # zodat de "niet opgeslagen"-indicator en de undo/redo-knoppen in de header
        # meteen kloppen, ook al gebeurt de bewerking hier in het middenpaneel.
        self._on_wijziging_header = on_wijziging_header or (lambda: None)

    def rebuild(self) -> None:
        self._container.clear()
        self._rows.clear()

        with self._container:
            ui.button(
                "+ Extra les toevoegen", icon="add", on_click=self._klik_extra_les_toevoegen
            ).props("flat dense color=primary").classes("q-mb-xs")

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

                rij = LessonRow(self._container, les, project, nieuwe_week, self._na_wijziging)
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

    def _na_wijziging(self, les_id: str) -> None:
        """Ververst deze les plus alle andere lessen in dezelfde ISO-week (bv. voor
        weekconflict-signalering, zie docs/PLAN.md fase 5), en meldt de header zodat de
        "niet opgeslagen"-indicator en undo/redo-knoppen meteen kloppen."""
        self._on_wijziging_header()
        if state.doc is None:
            return
        project = state.doc.project
        les = next((l for l in project.lessen if l.id == les_id), None)
        if les is None:
            self.rebuild()
            return
        jaar_week = les.datum.isocalendar()[:2]
        ids_in_week = [
            l.id for l in project.lessen if l.datum.isocalendar()[:2] == jaar_week
        ]
        self.refresh_lessen(ids_in_week)

    async def _klik_extra_les_toevoegen(self) -> None:
        if state.doc is None:
            return
        with ui.dialog() as dialoog, ui.card():
            ui.label("Extra les toevoegen").classes("text-subtitle1")
            datum_kiezer = ui.date(value=date.today().isoformat())
            with ui.row():
                begin_veld = ui.input("Begintijd (HH:MM)", value="10:00")
                eind_veld = ui.input("Eindtijd (HH:MM)", value="12:00")
            titel_veld = ui.input("Titel (bv. 'Open Les')").classes("full-width")
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props("flat")
                ui.button(
                    "Toevoegen",
                    on_click=lambda: dialoog.submit(
                        (datum_kiezer.value, begin_veld.value, eind_veld.value, titel_veld.value)
                    ),
                ).props("color=primary")

        resultaat = await dialoog
        if resultaat is None:
            return
        datum_str, begin_str, eind_str, titel = resultaat
        try:
            from ..domain.formatting import parse_nl_tijd

            datum_waarde = date.fromisoformat(datum_str)
            begin_tijd = parse_nl_tijd(begin_str)
            eind_tijd = parse_nl_tijd(eind_str)
        except ValueError:
            ui.notify(
                "Ongeldige datum of tijd. Gebruik het formaat HH:MM voor tijden.",
                type="negative",
            )
            return
        lb.voeg_extra_les_toe(datum_waarde, begin_tijd, eind_tijd, titel)
        ui.notify(f"Extra les toegevoegd op {format_datum_lang(datum_waarde)}.", type="positive")
        self.rebuild()
        self._on_wijziging_header()
