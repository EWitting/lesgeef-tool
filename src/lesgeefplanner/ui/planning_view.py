"""Het middenpaneel: de planning, altijd zichtbaar. Zie docs/DESIGN.md §4.7 en §2.6.

Ververst per rij (`refresh_les`) in plaats van de hele lijst opnieuw op te bouwen
(`rebuild`), zodat een enkele bewerking niet de hele DOM-boom opnieuw hoeft te tekenen --
dat was precies het probleem met de oude AG Grid-integratie. Roep `rebuild()` daarom NOOIT
aan na een gewone celwijziging (alleen bij het wisselen van project of scope)."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Callable

from nicegui import ui

from ..domain.analysis import Bevinding
from ..domain.beschikbaarheid import verzamel_beschikbaarheid
from ..domain.formatting import format_datum, format_tijd, format_tijdvak
from ..model.entities import Les, les_seizoen_id
from ..model.project import Project
from ..model.scope import Scope
from ..planner import bouw_request, los_op
from . import lesbewerkingen as lb
from .dialogen.diff_dialoog import DiffRegel, toon_diff_dialoog
from .dialogen.scope_balk import create_scope_balk
from .state import state
from .velden import tijd_veld

_WEEK_GRENS_STIJL = "border-top: 2px solid #7a9cc4;"
_GEEN_WEEK_GRENS_STIJL = "border-top: 1px solid transparent;"
_EVEN_WEEK_KLEUR = "#dce6f1"
_ONEVEN_WEEK_KLEUR = "#f0f0f0"
_PIN = "\U0001F4CC"
# Band die aangeeft of een les binnen de huidige Scope valt (docs/DESIGN.md §2.4) --
# zodat nooit onduidelijk is wat "Automatisch invullen"/een nieuwe ronde gaat raken.
_SCOPE_RAND_AAN = "border-left: 4px solid #3182ce;"
_SCOPE_RAND_UIT = "border-left: 4px solid transparent;"

_ERNST_RANG = {"fout": 3, "waarschuwing": 2, "info": 1}
_BESCHIKBAARHEID_KOP = {"ja": "Ja", "misschien": "Misschien", "onbekend": "Onbekend", "nee": "Nee"}
_ERNST_KLEUR = {"fout": "text-red-8", "waarschuwing": "text-orange-6", "info": "text-blue-6"}


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
        on_selecteer: Callable[[str], None],
        scope: Scope,
        peildatum: date,
    ) -> None:
        self._on_wijziging = on_wijziging
        self._on_selecteer = on_selecteer
        self._les_id = les.id
        # Vast per rij (verandert niet na constructie), dus apart bewaard i.p.v. steeds
        # opnieuw af te leiden -- ververs() moet 'm elke keer META de andere stijlen
        # meesturen, want .style(replace=...) vervangt de VOLLEDIGE inline stijl.
        self._week_grens_stijl = _WEEK_GRENS_STIJL if nieuwe_week else _GEEN_WEEK_GRENS_STIJL

        with container:
            # full-width: zonder dit neemt de rij alleen de breedte van zijn eigen inhoud
            # in (een q-row rekt van zichzelf niet uit), en verschilt de breedte per rij
            # net zo veel als het aantal getoonde slots (0 bij een vervallen les, anders
            # het maximum) -- dat gaf zowel een onbedoelde witruimte rechts van de tabel
            # als een rafelige rand tussen rijen onderling.
            with ui.row().classes("items-center q-px-sm full-width").style(
                "flex-wrap: nowrap; min-height: 32px;" + self._week_grens_stijl
            ) as self.root:
                with ui.row().classes("items-center cursor-pointer").style(
                    "flex-wrap: nowrap; gap: 4px;"
                ).on("click", lambda: self._on_selecteer(self._les_id)) as self.info_gebied:
                    self.stip = ui.icon("circle").classes("text-transparent").style(
                        "font-size: 9px; width: 12px;"
                    )
                    with self.stip:
                        self.stip_tooltip = ui.tooltip("")
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

                # margin-left: auto duwt de acties-knop altijd naar de rechterrand van de
                # (nu full-width) rij, ongeacht hoeveel slot-knoppen ervoor staan -- zo
                # eindigt elke rij op dezelfde plek in plaats van direct na de laatste slot.
                self.acties_btn = ui.button(icon="more_vert").props("flat dense size=sm").style(
                    "margin-left: auto;"
                )
                with self.acties_btn:
                    self.acties_menu = ui.menu()

        self.ververs(les, project, scope, peildatum)
        self.zet_bevindingen([])

    # ------------------------------------------------------------------

    def ververs(self, les: Les, project: Project, scope: Scope, peildatum: date) -> None:
        self._les_id = les.id
        even_week = les.datum.isocalendar()[1] % 2 == 0
        achtergrond = _EVEN_WEEK_KLEUR if even_week else _ONEVEN_WEEK_KLEUR
        vervallen = les.status == "vervallen"
        scope_rand = _SCOPE_RAND_AAN if scope.bevat(les, peildatum) else _SCOPE_RAND_UIT
        self.root.style(
            replace=(
                f"background: {achtergrond}; flex-wrap: nowrap; min-height: 32px; "
                f"{self._week_grens_stijl} {scope_rand}"
            )
        )
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
                knop = ui.button().props("flat dense no-caps size=sm").classes(
                    "les-slot-knop"
                ).style("width: 130px; justify-content: flex-start;")
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

    def zet_bevindingen(self, bevindingen: list[Bevinding]) -> None:
        """Kleurt de stip naar de hoogste ernst in `bevindingen` (leeg = onzichtbaar), met
        de titels als tooltip. Wordt door de inspector aangeroepen na elke analyse."""
        if not bevindingen:
            self.stip.classes(replace="text-transparent")
            self.stip_tooltip.set_text("")
            return
        hoogste = max(bevindingen, key=lambda b: _ERNST_RANG[b.ernst])
        self.stip.classes(replace=_ERNST_KLEUR[hoogste.ernst])
        self.stip_tooltip.set_text("; ".join(b.titel for b in bevindingen))

    def _ververs_slot(self, i: int, les: Les, project: Project) -> None:
        knop = self.slot_knoppen[i]
        menu = self.slot_menus[i]
        namen = {lg.id: lg.naam for lg in project.lesgevers}
        beschikbaarheid = verzamel_beschikbaarheid(project)

        bezet = i < len(les.toewijzingen)
        basis_stijl = "width: 130px; justify-content: flex-start;"
        if bezet:
            tw = les.toewijzingen[i]
            naam = namen.get(tw.lesgever_id, "? (onbekend)")
            knop.set_text(f"{_PIN} {naam}" if tw.vast else naam)
            if beschikbaarheid.get((tw.lesgever_id, les.id)) == "misschien":
                basis_stijl += " background: #fff3cd;"
        else:
            knop.set_text("—")
        knop.style(replace=basis_stijl)

        menu.clear()
        with menu:
            actieve_lesgevers = sorted(
                (lg for lg in project.lesgevers if lg.actief), key=lambda lg: lg.naam.lower()
            )
            if not actieve_lesgevers:
                ui.menu_item("Geen actieve lesgevers").props("disable")

            per_categorie: dict[str, list] = {"ja": [], "misschien": [], "onbekend": [], "nee": []}
            for lg in actieve_lesgevers:
                waarde = beschikbaarheid.get((lg.id, les.id)) or "onbekend"
                per_categorie[waarde].append(lg)

            for categorie in ("ja", "misschien", "onbekend", "nee"):
                groep = per_categorie[categorie]
                if not groep:
                    continue
                if len(actieve_lesgevers) > len(groep):  # kopregel alleen als er >1 groep is
                    ui.menu_item(_BESCHIKBAARHEID_KOP[categorie]).props("disable").classes(
                        "text-caption text-weight-bold"
                    )
                for lg in groep:
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
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props(
                    "flat no-caps"
                )
                ui.button(
                    "Vervalt", on_click=lambda: dialoog.submit(reden_veld.value)
                ).props("color=negative no-caps")

        reden = await dialoog
        if reden is None:
            return
        lb.markeer_vervallen(self._les_id, reden)
        self._on_wijziging(self._les_id)

    async def _klik_tijd_aanpassen(self, les: Les) -> None:
        with ui.dialog() as dialoog, ui.card():
            ui.label("Tijd aanpassen").classes("text-subtitle1")
            with ui.row():
                begin_veld = tijd_veld("Begintijd", format_tijd(les.begin_tijd))
                eind_veld = tijd_veld("Eindtijd", format_tijd(les.eind_tijd))
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props(
                    "flat no-caps"
                )
                ui.button(
                    "Opslaan",
                    on_click=lambda: dialoog.submit((begin_veld.value, eind_veld.value)),
                ).props("color=primary no-caps")

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
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props(
                    "flat no-caps"
                )
                ui.button(
                    "Opslaan", on_click=lambda: dialoog.submit(titel_veld.value)
                ).props("color=primary no-caps")

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
        self,
        container: ui.column,
        on_wijziging_header: Callable[[], None] | None = None,
        on_selecteer_les: Callable[[str], None] | None = None,
    ) -> None:
        self._container = container
        self._rows: dict[str, LessonRow] = {}
        # Wordt aangeroepen na elke bewerking, naast het verversen van de rij(en) zelf --
        # zodat de "niet opgeslagen"-indicator en de undo/redo-knoppen in de header
        # meteen kloppen, ook al gebeurt de bewerking hier in het middenpaneel.
        self._on_wijziging_header = on_wijziging_header or (lambda: None)
        # Wordt aangeroepen als de gebruiker op het datum/tijd-gebied van een rij klikt --
        # het inspectiepaneel (fase 5) toont dan de details van die les.
        self._on_selecteer_les = on_selecteer_les or (lambda les_id: None)

    def rebuild(self) -> None:
        self._container.clear()
        self._rows.clear()

        with self._container:
            with ui.column().classes("full-width").style(
                "padding: 12px 16px 8px 16px; gap: 8px; border-bottom: 1px solid #e0e0e0;"
            ):
                scope_balk_rij = ui.row().classes("q-gutter-sm items-center full-width")
                create_scope_balk(scope_balk_rij)
                with ui.row().classes("q-gutter-sm items-center"):
                    ui.button(
                        "Automatisch invullen", icon="auto_fix_high",
                        on_click=self._klik_automatisch_invullen,
                    ).props("dense color=primary no-caps")

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
                    "Nog geen lessen. Stel eerst lessenreeksen en een weekrooster in."
                ).classes("text-grey-6 q-pa-md")
            return

        seizoen_naam = {s.id: s.naam for s in project.seizoenen}

        vorige_seizoen_id: object = object()
        vorige_week: int | None = None

        with self._container:
            for les in lessen:
                seizoen_id = les_seizoen_id(les)
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

                rij = LessonRow(
                    self._container, les, project, nieuwe_week,
                    self._na_wijziging, self._on_selecteer_les,
                    state.scope, state.peildatum(),
                )
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
        rij.ververs(les, project, state.scope, state.peildatum())

    def refresh_lessen(self, les_ids) -> None:
        for les_id in les_ids:
            self.refresh_les(les_id)

    def stel_bevindingen_in(self, per_les: dict[str, list[Bevinding]]) -> None:
        """Zet de issue-stip per rij. Aangeroepen door de inspector na elke analyse."""
        for les_id, rij in self._rows.items():
            rij.zet_bevindingen(per_les.get(les_id, []))

    def scroll_en_licht_op(self, les_id: str) -> None:
        """Scrollt naar de rij en licht hem 2 seconden op (docs/DESIGN.md §5: klikken op
        een bevinding brengt je bij het juiste object)."""
        rij = self._rows.get(les_id)
        if rij is None:
            return
        ui.run_javascript(
            f'getElement({rij.root.id}).$el.scrollIntoView('
            f'{{behavior: "smooth", block: "center"}});'
        )
        rij.root.classes(add="rij-opgelicht")
        ui.timer(2.0, lambda: rij.root.classes(remove="rij-opgelicht"), once=True)

    def _na_wijziging(self, les_id: str) -> None:
        """Ververst deze les plus alle andere lessen in dezelfde ISO-week (bv. voor
        weekconflict-signalering, zie docs/PLAN.md fase 5), en meldt de header zodat de
        "niet opgeslagen"-indicator en undo/redo-knoppen meteen kloppen.

        Maakt ook het laatste solver-resultaat ongeldig: een handmatige wijziging (hier,
        niet via _klik_automatisch_invullen) maakt de oude score-opbouw ("Waarom deze
        score?") niet meer kloppend met de werkelijke toewijzingen, dus die moet niet
        stiekem een verouderd getal blijven tonen."""
        state.laatste_plan_result = None
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

    async def _klik_automatisch_invullen(self) -> None:
        """Lost de huidige scope op met de solver en toont het resultaat als een
        voorstel-diff die de gebruiker per les moet bevestigen -- de solver zelf muteert
        niets (docs/DESIGN.md §4.2)."""
        if state.doc is None:
            return
        project = state.doc.project
        scope = state.scope
        peildatum = state.peildatum()

        request = bouw_request(project, scope, peildatum)
        if not request.lessen_in_scope:
            ui.notify("Geen lessen in de huidige scope om automatisch in te vullen.", type="warning")
            return

        melding = ui.notification(
            "Solver bezig...", spinner=True, timeout=None, type="ongoing"
        )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, los_op, request)
        finally:
            melding.dismiss()

        state.laatste_plan_result = result

        if result.status == "onhaalbaar":
            ui.notify(
                "Geen haalbare oplossing gevonden. Controleer de beschikbaarheid en het "
                "minimum/maximum aantal lesgevers per les in de configuratie.",
                type="negative",
                multi_line=True,
            )
            return
        if not result.minimum_afgedwongen:
            ui.notify(
                "Let op: voor sommige lessen kon het minimum aantal lesgevers niet gehaald "
                "worden. Bekijk het voorstel voor details.",
                type="warning",
                multi_line=True,
            )

        lesgever_naam = {lg.id: lg.naam for lg in project.lesgevers}
        les_by_id = {les.id: les for les in request.lessen_in_scope}
        regels: list[DiffRegel] = []
        for les_id, nieuwe_ids in result.toewijzingen.items():
            les = les_by_id[les_id]
            oude_ids = [tw.lesgever_id for tw in les.toewijzingen]
            if set(nieuwe_ids) == set(oude_ids):
                continue
            oud_tekst = ", ".join(lesgever_naam.get(i, "? (onbekend)") for i in oude_ids) or "leeg"
            nieuw_tekst = ", ".join(lesgever_naam.get(i, "? (onbekend)") for i in nieuwe_ids) or "leeg"
            regels.append(
                DiffRegel(
                    id=les_id,
                    omschrijving=f"{format_datum(les.datum)} {format_tijd(les.begin_tijd)}: "
                    f"{oud_tekst} → {nieuw_tekst}",
                )
            )
        regels.sort(key=lambda r: les_by_id[r.id].datum)

        gekozen = await toon_diff_dialoog(
            f"Voorstel automatisch invullen ({len(regels)} lessen gewijzigd)",
            regels,
            toepassen_label="Toepassen",
        )
        if gekozen is None:
            return

        lb.pas_solverresultaat_toe(gekozen, result.toewijzingen)
        self.rebuild()
        self._on_wijziging_header()
        ui.notify(f"{len(gekozen)} lessen bijgewerkt.", type="positive")
