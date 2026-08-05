from datetime import date, time

from lesgeefplanner.model import (
    Les,
    Lesgever,
    Project,
    Scope,
    Seizoen,
    Toewijzing,
    WeekSlot,
)


def test_project_json_roundtrip():
    project = Project(
        naam="Testjaar",
        weekrooster=[WeekSlot(dag=2, begin_tijd=time(16, 0), eind_tijd=time(19, 0))],
        seizoenen=[
            Seizoen(naam="Voorseizoen 1", begin=date(2026, 4, 19), eind=date(2026, 5, 10)),
        ],
        lesgevers=[Lesgever(naam="Anne", ervaren=True)],
    )
    les = Les(
        datum=date(2026, 4, 22),
        begin_tijd=time(16, 0),
        eind_tijd=time(19, 0),
        seizoen_id=project.seizoenen[0].id,
    )
    les.toewijzingen.append(Toewijzing(lesgever_id=project.lesgevers[0].id, vast=True))
    project.lessen.append(les)

    ruw = project.model_dump_json()
    herladen = Project.model_validate_json(ruw)

    assert herladen.naam == "Testjaar"
    assert herladen.lessen[0].begin_tijd == time(16, 0)
    assert herladen.lessen[0].toewijzingen[0].vast is True
    assert herladen.seizoenen[0].weekrooster is None


def test_seizoen_lege_weekrooster_is_niet_none():
    """Een expliciet lege lijst moet onderscheiden blijven van 'geen eigen weekrooster'."""
    seizoen = Seizoen(naam="PKursus", begin=date(2026, 3, 16), eind=date(2026, 4, 19),
                       weekrooster=[])
    ruw = seizoen.model_dump_json()
    herladen = Seizoen.model_validate_json(ruw)
    assert herladen.weekrooster == []
    assert herladen.weekrooster is not None


def test_scope_bevat():
    seizoen_id = "s1"
    les_in = Les(datum=date(2026, 4, 22), begin_tijd=time(16, 0), eind_tijd=time(19, 0),
                 seizoen_id=seizoen_id)
    les_ander_seizoen = les_in.model_copy(update={"seizoen_id": "s2"})
    les_verleden = les_in.model_copy(update={"datum": date(2026, 1, 1)})

    scope = Scope(seizoen_ids=[seizoen_id], alleen_toekomst=True)
    peildatum = date(2026, 4, 1)

    assert scope.bevat(les_in, peildatum) is True
    assert scope.bevat(les_ander_seizoen, peildatum) is False
    assert scope.bevat(les_verleden, peildatum) is False


def test_extra_forbid():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Lesgever(naam="X", onbekend_veld=1)
