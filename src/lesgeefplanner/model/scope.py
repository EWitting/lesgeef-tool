"""Scope: welk deel van het jaar een actie raakt. Zie docs/DESIGN.md §3.6 en §2.4."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .entities import Les


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seizoen_ids: list[str] | None = None  # None = alle seizoenen
    van: date | None = None
    tot: date | None = None
    alleen_toekomst: bool = True

    def bevat(self, les: "Les", peildatum: date) -> bool:
        """De enige plek waar scope-logica staat.
        Volgorde: seizoen-filter -> datumbereik -> alleen_toekomst."""
        if self.seizoen_ids is not None:
            if les.seizoen_id not in self.seizoen_ids:
                return False
        if self.van is not None and les.datum < self.van:
            return False
        if self.tot is not None and les.datum > self.tot:
            return False
        if self.alleen_toekomst and les.datum < peildatum:
            return False
        return True
