"""Fase 3 acceptatiecriterium (docs/PLAN.md): een volledig rooster met de hand maken,
afsluiten, heropenen -- alles moet er nog staan."""
from datetime import date, time
from pathlib import Path

from lesgeefplanner.domain.calendar import bereken_kalender_diff, pas_kalender_diff_toe
from lesgeefplanner.model import Lesgever, Seizoen, WeekSlot
from lesgeefplanner.store.document import Document
from lesgeefplanner.ui import lesbewerkingen as lb
from lesgeefplanner.ui.state import AppState


def test_volledig_handmatig_rooster_overleeft_opslaan_en_heropenen(tmp_path: Path, monkeypatch):
    st = AppState()
    monkeypatch.setattr(lb, "state", st)

    st.nieuw_project("Testjaar")
    with st.doc.muteer("setup"):
        st.doc.project.weekrooster = [
            WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0)),
        ]
        st.doc.project.seizoenen.append(
            Seizoen(naam="Voorseizoen 1", begin=date(2026, 4, 19), eind=date(2026, 5, 10))
        )
        anne = Lesgever(naam="Anne", ervaren=True)
        bob = Lesgever(naam="Bob")
        st.doc.project.lesgevers.extend([anne, bob])

    diff = bereken_kalender_diff(st.doc.project)
    with st.doc.muteer("kalender gegenereerd"):
        pas_kalender_diff_toe(st.doc.project, diff, {l.id for l in diff.toe_te_voegen})
    # Woensdagen tussen 19 apr (zondag) en 10 mei 2026: 22 apr, 29 apr, 6 mei.
    assert len(st.doc.project.lessen) == 3

    lessen = sorted(st.doc.project.lessen, key=lambda l: l.datum)

    # Handmatig volledig inroosteren
    lb.wijs_lesgever_toe(lessen[0].id, 0, anne.id)
    lb.wijs_lesgever_toe(lessen[0].id, 1, bob.id)
    lb.wijs_lesgever_toe(lessen[1].id, 0, bob.id)
    lb.wissel_vast(lessen[1].id, 0)  # weer losmaken
    lb.markeer_vervallen(lessen[2].id, "Weerbericht")
    lb.wijzig_titel(lessen[2].id, "Laatste les (vervallen)")
    extra_id = lb.voeg_extra_les_toe(date(2026, 5, 16), time(10, 0), time(12, 0), "Open Les")
    lb.wijs_lesgever_toe(extra_id, 0, anne.id)

    pad = tmp_path / "test.lesplan"
    st.doc.opslaan(pad)

    heropend = Document.open(pad)
    project = heropend.project

    def vind(les_id):
        return next(l for l in project.lessen if l.id == les_id)

    les0 = vind(lessen[0].id)
    assert {tw.lesgever_id for tw in les0.toewijzingen} == {anne.id, bob.id}
    assert all(tw.vast for tw in les0.toewijzingen)
    assert les0.beschermd is True

    les1 = vind(lessen[1].id)
    assert les1.toewijzingen[0].vast is False

    les2 = vind(lessen[2].id)
    assert les2.status == "vervallen"
    assert les2.vervallen_reden == "Weerbericht"
    assert les2.toewijzingen == []
    assert les2.titel == "Laatste les (vervallen)"

    extra = vind(extra_id)
    assert extra.soort == "extra"
    assert extra.titel == "Open Les"
    assert extra.toewijzingen[0].lesgever_id == anne.id

    assert len(project.lessen) == 4
    assert project.lesgevers[0].naam == "Anne"
    assert project.lesgevers[0].ervaren is True
