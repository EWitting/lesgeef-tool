from datetime import date, time

import pytest

from lesgeefplanner.domain.formatting import (
    format_datum,
    format_datum_lang,
    format_tijdvak,
    parse_nl_maand,
    parse_nl_tijd,
)


def test_format_datum():
    # zondag 19 april 2026
    assert format_datum(date(2026, 4, 19)) == "zo 19 apr"


def test_format_datum_lang():
    assert format_datum_lang(date(2026, 4, 19)) == "zondag 19 april 2026"


def test_format_tijdvak():
    assert format_tijdvak(time(16, 0), time(19, 0)) == "16:00 - 19:00"


def test_parse_nl_maand_kort_en_lang():
    assert parse_nl_maand("okt") == 10
    assert parse_nl_maand("oktober") == 10
    assert parse_nl_maand("Okt") == 10


def test_parse_nl_maand_onbekend():
    with pytest.raises(ValueError):
        parse_nl_maand("xxx")


def test_parse_nl_tijd():
    assert parse_nl_tijd("16:00") == time(16, 0)
