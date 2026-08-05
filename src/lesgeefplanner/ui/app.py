"""NiceGUI-app: startscherm of de drie-zone-lay-out (docs/DESIGN.md §2.6).

header: projectnaam + opgeslagen-indicator, undo/redo, solver-instellingen, opslaan, sluiten.
links:  navigatie (Jaarplanning, Lesgevers, Beschikbaarheid) met een puntje voor aandacht/
        nog-niet-begonnen -- vertrouwde sidebar-lijst i.p.v. tabs (zie docs/BESLISSINGEN.md).
midden: de planning, ALTIJD zichtbaar (dit is het hart van de app) + acties die op de
        zichtbare planning werken (automatisch invullen, delen via Excel).
rechts: inspector -- status/les/persoon."""
from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui import ui
from platformdirs import user_documents_dir

from . import stappen
from .bestandsdialoog import kies_bestand_opslaan, native_beschikbaar
from .dialogen.excel import exporteer_excel, open_import_dialoog
from .dialogen.jaarplanning import create_jaarplanning_paneel
from .dialogen.lesgevers import create_lesgevers_paneel
from .dialogen.rondes import create_rondes_paneel
from .dialogen.solver_config import create_solver_config_knop
from .inspector import Inspector
from .planning_view import PlanningView
from .startscherm import create_startscherm
from .state import state

_LINKS_SPLITTER_STANDAARD = 19.0  # procent van de vensterbreedte
_RECHTS_SPLITTER_STANDAARD = 24.0  # procent van (midden + rechts) -- reverse=True, dus dit IS het rechterpaneel

# (sectie-id, icoon, label, sleutel in stappen.alle_stappen()) -- de navigatie ZELF, in
# gebruiksvolgorde. "Inroosteren" en "Delen" staan bewust niet in deze lijst: inroosteren
# gebeurt in het altijd-zichtbare middenpaneel, delen is een actie op de planning (zie het
# middenpaneel), geen aparte sectie om in rond te lopen.
_SECTIES: list[tuple[str, str, str, str]] = [
    ("jaarplanning", "calendar_month", "Jaarplanning", "Jaarplanning"),
    ("lesgevers", "group", "Lesgevers", "Lesgevers"),
    ("beschikbaarheid", "fact_check", "Beschikbaarheid", "Beschikbaarheid"),
]
_STATUS_STIP_KLEUR = {"klaar": "transparent", "aandacht": "#f59e0b", "leeg": "#cbd5e0"}
_STATUS_STIP_UITLEG = {
    "klaar": "Klaar -- niets te doen.",
    "aandacht": "Aandacht nodig.",
    "leeg": "Nog niet begonnen.",
}


@ui.page("/")
def index() -> None:
    ui.add_head_html(
        "<style>"
        ".rij-opgelicht { outline: 2px solid #f6ad55; outline-offset: -2px; }"
        # NiceGUI geeft de pagina-inhoud standaard 1rem padding (bedoeld voor gewone
        # scroll-pagina's) -- deze app tekent zijn eigen edge-to-edge drie-zone-lay-out en
        # rekent zelf met 100vh, dus die padding moet weg (anders klopt de vh-berekening
        # niet en ontstaat er een witrand rond de hele app).
        ".nicegui-content { padding: 0 !important; margin: 0 !important; height: 100vh; }"
        # Navigatie-rij in de linkerrail: vertrouwd "sidebar-lijst"-patroon (Bootstrap/
        # VS Code/Notion) -- een vaste linker accentrand die van transparant naar de
        # primaire kleur springt bij de actieve sectie, zodat de breedte niet verspringt.
        ".nav-item, .list-item { transition: background-color .12s ease; cursor: pointer; }"
        ".nav-item:hover, .list-item:hover { background: rgba(0,0,0,0.05); }"
        # Toetsenbordfocus (Tab) moet zichtbaar zijn -- dit zijn <div>'s met een klik-
        # handler, geen <button>/<a>, dus zonder deze regel is er anders geen enkel
        # focus-signaal voor wie met het toetsenbord navigeert.
        ".nav-item:focus-visible, .list-item:focus-visible { outline: 2px solid #1976d2; "
        "outline-offset: -2px; }"
        ".nav-item { border-left: 3px solid transparent; border-radius: 0 8px 8px 0; }"
        ".nav-item.nav-actief { background: rgba(25,118,210,0.10); border-left-color: "
        "#1976d2; }"
        ".nav-item.nav-actief .nav-label { font-weight: 600; }"
        # .list-item: hetzelfde hover/focus-gedrag maar los van de linkerrail (bv. "Recent
        # geopend" op het startscherm) -- symmetrische ronding, geen accentrand die alleen
        # bij een tegen-de-rand-liggende rail zin heeft.
        ".list-item { border-radius: 8px; }"
        # Lesgever-knoppen in het rooster hebben een vaste breedte (zodat de rij niet
        # per les breder/smaller wordt) -- een lange naam moet dan afkappen met "...", niet
        # de rij uit elkaar duwen of onleesbaar overlappen.
        ".les-slot-knop .q-btn__content > span { overflow: hidden; text-overflow: "
        "ellipsis; white-space: nowrap; display: block; max-width: 100%; }"
        # De sleepbalk van een q-splitter is standaard maar 1px en bijna onzichtbaar tegen
        # een witte achtergrond -- zonder duidelijk zichtbare balk (en cursor) heeft niemand
        # door dat er iets sleepbaars zit. Iets breder, een grijze kleur, donkerder bij
        # hover/actief slepen, en een expliciete cursor (voor het geval iets anders 'm zou
        # overschrijven).
        ".q-splitter__separator { background: #d5dbe0 !important; width: 6px !important; "
        "cursor: col-resize !important; }"
        ".q-splitter__separator:hover, .q-splitter__separator--active "
        "{ background: #90a4ae !important; }"
        # Het in-/uitklap-knopje middenin de sleepbalk (zie `_maak_inklap_knop`) moet er
        # overheen kunnen zonder zelf de sleepbalk te blokkeren.
        ".splitter-inklap-knop { position: absolute; top: 50%; left: 50%; "
        "transform: translate(-50%, -50%); z-index: 2; }"
        "</style>"
    )
    root = ui.column().classes("w-full no-wrap").style(
        "height: 100vh; margin: 0; padding: 0; gap: 0;"
    )

    def toon_startscherm() -> None:
        root.clear()
        with root:
            create_startscherm(on_klaar=toon_hoofdscherm)

    def toon_hoofdscherm() -> None:
        root.clear()
        with root:
            _bouw_hoofdlayout(on_sluiten=toon_startscherm)

    if state.doc is not None:
        toon_hoofdscherm()
    else:
        toon_startscherm()


def _bouw_hoofdlayout(on_sluiten) -> None:
    links_zichtbaar = {"waarde": True, "laatste_breedte": _LINKS_SPLITTER_STANDAARD}
    rechts_zichtbaar = {"waarde": True, "laatste_breedte": _RECHTS_SPLITTER_STANDAARD}

    # Bewust een gewone ui.row() in plaats van ui.header(): ui.header() is een top-level
    # layout-element dat NIET genest mag worden in root (een ui.column()), en we willen de
    # volledige lay-out zelf onder controle houden binnen root.
    # flex-wrap (i.p.v. no-wrap): op een smal venster/laptopscherm moeten de knoppen naar
    # een tweede regel kunnen overlopen -- anders vallen ze letterlijk buiten beeld en is
    # bv. "Sluiten" onbereikbaar (zie docs/BESLISSINGEN.md, "header-robuustheid").
    with ui.row().classes("items-center justify-between bg-primary full-width").style(
        "padding: 10px 20px; margin: 0; flex-shrink: 0; flex-wrap: wrap; row-gap: 6px; "
        "box-shadow: 0 1px 4px rgba(0,0,0,0.25); z-index: 1;"
    ):
        with ui.row().classes("items-center q-gutter-sm"):
            projectnaam_label = ui.label(state.doc.project.naam).classes(
                "text-h6 text-white"
            )
            opgeslagen_label = ui.label().classes("text-caption text-white").style(
                "opacity: 0.85;"
            )

        with ui.row().classes("items-center q-gutter-md").style(
            "flex-wrap: wrap; row-gap: 6px; justify-content: flex-end;"
        ):
            with ui.row().classes("items-center q-gutter-xs"):
                undo_btn = ui.button(icon="undo", on_click=lambda: _ongedaan_maken()).props(
                    "flat color=white dense round"
                )
                with undo_btn:
                    undo_tooltip = ui.tooltip("Ongedaan maken (Ctrl+Z)")
                redo_btn = ui.button(icon="redo", on_click=lambda: _opnieuw()).props(
                    "flat color=white dense round"
                )
                with redo_btn:
                    redo_tooltip = ui.tooltip("Opnieuw uitvoeren (Ctrl+Y)")
                with ui.element("div") as solver_config_knop_houder:
                    pass
                create_solver_config_knop(solver_config_knop_houder, kleur="white")
            ui.button(
                "Exporteren", icon="download", on_click=lambda: exporteer_excel()
            ).props("flat color=white dense no-caps").tooltip(
                "Exporteer de planning naar Excel om te delen via Google Drive."
            )
            ui.button(
                "Importeren", icon="upload_file", on_click=lambda: open_import_dialoog()
            ).props("flat color=white dense no-caps").tooltip(
                "Haal wijzigingen terug die rechtstreeks in de geëxporteerde sheet zijn "
                "gemaakt."
            )
            ui.button(
                "Opslaan", icon="save", on_click=lambda: _opslaan()
            ).props("flat color=white dense no-caps").tooltip("Opslaan (Ctrl+S)")
            ui.button(
                "Sluiten", icon="close", on_click=on_sluiten
            ).props("flat color=white dense no-caps")

    actieve_sectie = {"waarde": _SECTIES[0][0]}
    nav_rijen: dict[str, ui.row] = {}
    nav_stippen: dict[str, ui.element] = {}
    nav_stip_tooltips: dict[str, ui.tooltip] = {}
    secties: dict[str, ui.column] = {}

    def _kies_sectie(sectie_id: str) -> None:
        actieve_sectie["waarde"] = sectie_id
        for sid, rij in nav_rijen.items():
            rij.classes(add="nav-actief" if sid == sectie_id else "", remove="" if sid == sectie_id else "nav-actief")
        for sid, paneel in secties.items():
            paneel.set_visibility(sid == sectie_id)

    # Twee geneste, sleepbare splitters i.p.v. vaste pixel-breedtes -- de linkerrail en het
    # gezondheidspaneel hebben allebei content die niet bij elke schermbreedte/lettergrootte
    # even veel ruimte nodig heeft, dus de gebruiker mag zelf slepen i.p.v. dat wij een
    # vaste breedte gokken. `limits` in procent van de beschikbare breedte; 0 als ondergrens
    # op de buitenste splitter zodat de linkerrail ook volledig dichtgesleept kan worden
    # (en de hamburger-knop hierboven precies datzelfde doet via `_toggle`).
    buiten_splitter = ui.splitter(value=_LINKS_SPLITTER_STANDAARD, limits=(0, 45)).classes(
        "w-full"
    ).style("flex: 1; margin: 0; min-height: 0; height: 100%;")
    _maak_inklap_knop(buiten_splitter, links_zichtbaar, omgekeerd=False)
    with buiten_splitter:
        with buiten_splitter.before:
            # align-self: stretch -- NiceGUI geeft een splitter-paneel (net als elke
            # column/row) standaard "align-items: flex-start", waardoor dit kind anders
            # krimpt tot de breedte van zijn eigen inhoud i.p.v. de (correct berekende!)
            # breedte die de splitter 'm toekent -- dát gaf de dode ruimte tussen de
            # scrollbar en de paneelrand die breder werd naarmate je verder sleepte.
            with ui.column().style(
                "height: 100%; overflow-y: auto; overflow-x: hidden; "
                "border-right: 1px solid #e0e0e0; padding: 12px 12px 16px 12px; margin: 0; "
                "gap: 12px; align-self: stretch; width: 100%;"
            ):
                with ui.column().classes("full-width").style("gap: 2px;"):
                    for sectie_id, icoon, label, _stap_sleutel in _SECTIES:
                        with ui.row().classes(
                            "items-center cursor-pointer full-width nav-item"
                        ).style("padding: 10px 12px; gap: 10px;").props(
                            "tabindex=0"
                        ).on(
                            "click", lambda s=sectie_id: _kies_sectie(s)
                        ).on(
                            "keydown.enter", lambda s=sectie_id: _kies_sectie(s)
                        ) as rij:
                            ui.icon(icoon).classes("text-grey-8")
                            ui.label(label).classes("text-body2 nav-label").style("flex: 1;")
                            stip = ui.element("div").style(
                                "width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;"
                            )
                            with stip:
                                stip_tooltip = ui.tooltip("")
                        nav_rijen[sectie_id] = rij
                        nav_stippen[sectie_id] = stip
                        nav_stip_tooltips[sectie_id] = stip_tooltip

                ui.separator()

                with ui.column().classes("full-width") as jaarplanning_paneel:
                    create_jaarplanning_paneel(jaarplanning_paneel)
                with ui.column().classes("full-width") as lesgevers_paneel:
                    create_lesgevers_paneel(lesgevers_paneel)
                with ui.column().classes("full-width") as rondes_paneel:
                    create_rondes_paneel(rondes_paneel)
                secties.update({
                    "jaarplanning": jaarplanning_paneel, "lesgevers": lesgevers_paneel,
                    "beschikbaarheid": rondes_paneel,
                })
                _kies_sectie(actieve_sectie["waarde"])

        with buiten_splitter.after:
            # reverse=True: `value` is hiermee het percentage van het RECHTERpaneel (i.p.v.
            # het middenpaneel) -- zo betekent "0" voor beide splitters hetzelfde ("dit
            # paneel dichtgeklapt"), en werkt dezelfde `_toggle`/`_maak_inklap_knop` voor
            # links én rechts zonder aparte richtingslogica. limits ondergrens MOET 0 zijn
            # (niet bv. 10) -- de splitter klemt `set_value()` net zo goed vast aan de
            # limits als slepen met de muis, dus met een ondergrens > 0 kon dit paneel
            # nooit volledig dichtklappen.
            binnen_splitter = ui.splitter(
                value=_RECHTS_SPLITTER_STANDAARD, limits=(0, 50), reverse=True
            ).style("height: 100%;")
            _maak_inklap_knop(binnen_splitter, rechts_zichtbaar, omgekeerd=True)
            with binnen_splitter:
                with binnen_splitter.before:
                    # gap: 0 -- een ui.column() heeft standaard 1rem verticale ruimte
                    # tussen kinderen (voor gewone formulieren bedoeld); de lesrijen moeten
                    # strak tegen elkaar staan, dus dat moet hier expliciet uit.
                    with ui.column().style(
                        "height: 100%; overflow-y: auto; overflow-x: hidden; padding: 0; "
                        "margin: 0; min-width: 0; gap: 0; align-self: stretch; width: 100%;"
                    ) as midden_paneel:
                        planning_view = PlanningView(
                            midden_paneel,
                            on_wijziging_header=lambda: _ververs_na_wijziging(),
                            on_selecteer_les=lambda les_id: inspector.toon_les(les_id),
                        )
                        planning_view.rebuild()

                with binnen_splitter.after:
                    with ui.column().style(
                        "height: 100%; overflow-y: auto; overflow-x: hidden; padding: 16px; "
                        "margin: 0; align-self: stretch; width: 100%;"
                    ) as rechts_paneel:
                        inspector = Inspector(rechts_paneel, planning_view)

    def ververs_header() -> None:
        assert state.doc is not None
        projectnaam_label.set_text(state.doc.project.naam)
        opgeslagen_label.set_text("Niet opgeslagen" if state.doc.gewijzigd else "Opgeslagen")

        volgende_undo = state.doc.volgende_undo_beschrijving()
        undo_btn.props(remove="disable", add="disable" if volgende_undo is None else "")
        undo_tooltip.set_text(
            f"Ongedaan maken: {volgende_undo} (Ctrl+Z)" if volgende_undo else "Niets om ongedaan te maken"
        )

        volgende_redo = state.doc.volgende_redo_beschrijving()
        redo_btn.props(remove="disable", add="disable" if volgende_redo is None else "")
        redo_tooltip.set_text(
            f"Opnieuw uitvoeren: {volgende_redo} (Ctrl+Y)" if volgende_redo else "Niets om opnieuw te doen"
        )

        statussen = stappen.alle_stappen(state.doc.project, state.peildatum())
        for sectie_id, _icoon, _label, stap_sleutel in _SECTIES:
            status = statussen[stap_sleutel]
            nav_stippen[sectie_id].style(f"background: {_STATUS_STIP_KLEUR[status]};")
            nav_stip_tooltips[sectie_id].set_text(_STATUS_STIP_UITLEG[status])

    def _ververs_na_wijziging() -> None:
        """Ververst header (opgeslagen-indicator, undo/redo), inspectiepaneel (bevindingen,
        issue-stippen) en de linkerrail (lesgevers/rondes kunnen bv. bij undo weer een
        andere stand hebben) -- na ELKE wijziging aan het project, ongeacht of die via het
        middenpaneel, de linkerrail, undo/redo, of de solver kwam."""
        ververs_header()
        inspector.render()
        create_jaarplanning_paneel(jaarplanning_paneel)
        create_lesgevers_paneel(lesgevers_paneel)
        create_rondes_paneel(rondes_paneel)

    def _ongedaan_maken() -> None:
        assert state.doc is not None
        beschrijving = state.doc.ongedaan_maken()
        if beschrijving is not None:
            ui.notify(f"Ongedaan gemaakt: {beschrijving}", type="info")
            # Kan zowel een handmatige wijziging als de toepassing van een solver-resultaat
            # ongedaan maken -- in beide gevallen klopt "Waarom deze score?" niet meer met
            # de huidige toewijzingen, dus niet stiekem een verouderd getal laten staan.
            state.laatste_plan_result = None
            planning_view.rebuild()
            _ververs_na_wijziging()

    def _opnieuw() -> None:
        assert state.doc is not None
        beschrijving = state.doc.opnieuw()
        if beschrijving is not None:
            ui.notify(f"Opnieuw uitgevoerd: {beschrijving}", type="info")
            state.laatste_plan_result = None
            planning_view.rebuild()
            _ververs_na_wijziging()

    async def _opslaan() -> None:
        assert state.doc is not None
        if state.doc.pad is None:
            await _opslaan_als()
            return
        state.opslaan()
        ui.notify("Opgeslagen.", type="positive")
        ververs_header()

    async def _opslaan_als() -> None:
        assert state.doc is not None
        standaardnaam = f"{state.doc.project.naam}.lesplan"
        if native_beschikbaar():
            pad = await kies_bestand_opslaan(standaardnaam)
            if pad is None:
                return
        else:
            pad = await _vraag_pad_via_dialoog(standaardnaam)
            if pad is None:
                return
        state.opslaan(pad)
        ui.notify(f"Opgeslagen als {pad}", type="positive")
        ververs_header()

    async def _vraag_pad_via_dialoog(standaardnaam: str) -> Path | None:
        """Tekstveld-fallback voor als er geen native venster is (bv. tijdens ontwikkelen)."""
        standaardpad = str(Path(user_documents_dir()) / standaardnaam)
        with ui.dialog() as dialoog, ui.card():
            ui.label("Opslaan als").classes("text-subtitle1")
            veld = ui.input("Bestandspad", value=standaardpad).classes("full-width").style(
                "width: 420px;"
            )
            with ui.row().classes("q-mt-sm justify-end full-width"):
                ui.button("Annuleren", on_click=lambda: dialoog.submit(None)).props(
                    "flat no-caps"
                )
                ui.button(
                    "Opslaan", on_click=lambda: dialoog.submit(veld.value)
                ).props("color=primary no-caps")
        resultaat = await dialoog
        return Path(resultaat) if resultaat else None

    def _op_toets(e) -> None:
        if not e.action.keydown or not e.modifiers.ctrl or e.modifiers.shift:
            return
        if e.key == "z":
            _ongedaan_maken()
        elif e.key == "y":
            _opnieuw()
        elif e.key == "s":
            # _opslaan is async (kan een bestandsdialoog tonen bij de allereerste keer
            # opslaan) -- _op_toets zelf is een gewone (sync) keyboard-callback, dus moet
            # 'm expliciet als taak inplannen i.p.v. de coroutine hier direct aan te roepen.
            asyncio.create_task(_opslaan())

    ui.keyboard(on_key=_op_toets)

    state.on_change(lambda: (planning_view.rebuild(), _ververs_na_wijziging()))
    ververs_header()
    ui.timer(5.0, lambda: _autosave_tick(ververs_header))


def _autosave_tick(ververs_header) -> None:
    if state.doc is None:
        return
    if state.doc.autosave_indien_nodig():
        ververs_header()


def _toggle(splitter: ui.splitter, toestand: dict) -> None:
    """Klapt een paneel in/uit door de sleepbare splitter zelf naar 0 te zetten (i.p.v.
    de inhoud te verbergen) -- zo blijft precies dezelfde sleepbalk werken, en onthoudt
    dichtklappen de laatst gesleepte breedte om bij het weer openen terug te zetten.
    Werkt voor beide splitters omdat `binnen_splitter` `reverse=True` heeft: 0 betekent
    voor allebei "dit paneel dichtgeklapt", nooit "het andere paneel is dicht"."""
    toestand["waarde"] = not toestand["waarde"]
    if toestand["waarde"]:
        splitter.set_value(toestand["laatste_breedte"])
    else:
        if splitter.value and splitter.value > 3:
            toestand["laatste_breedte"] = splitter.value
        splitter.set_value(0)


def _pijl_icoon(open_: bool, omgekeerd: bool) -> str:
    """Welke kant de pijl op wijst hangt af van welke kant het paneel dichtklapt: voor de
    linkerrail wijst 'm naar links als hij open is (klik om dichter naar links te klappen)
    en naar rechts als hij dicht is (klik om weer open te klappen); voor het rechterpaneel
    precies gespiegeld (`omgekeerd=True`)."""
    if open_:
        return "chevron_right" if omgekeerd else "chevron_left"
    return "chevron_left" if omgekeerd else "chevron_right"


def _maak_inklap_knop(splitter: ui.splitter, toestand: dict, omgekeerd: bool) -> None:
    """Een pijltje middenin de sleepbalk zelf om het paneel in/uit te klappen -- naar
    verwachting intuïtiever dan een los hamburger-icoon in de header, en dit werkt nu voor
    ZOWEL de linkerrail als het rechterpaneel (dat had voorheen geen in/uitklap-knop)."""
    with splitter.separator:
        knop = ui.button(icon=_pijl_icoon(toestand["waarde"], omgekeerd)).props(
            "flat dense round size=sm color=grey-8"
        ).classes("splitter-inklap-knop")

    def _klik() -> None:
        _toggle(splitter, toestand)
        knop.set_icon(_pijl_icoon(toestand["waarde"], omgekeerd))

    knop.on("click", _klik)
    knop.tooltip("Paneel in-/uitklappen")
