"""Bestandskeuze: native OS-dialoog in de gepakte app, tekstveld-fallback in browsermodus
(bv. tijdens ontwikkelen, waar geen pywebview-venster draait). Zie docs/BESLISSINGEN.md voor
de afweging native-venster versus browsertab."""
from __future__ import annotations

from pathlib import Path

from nicegui import app


def native_beschikbaar() -> bool:
    try:
        import webview  # noqa: F401
    except ImportError:
        return False
    return getattr(app.native, "main_window", None) is not None


async def kies_bestand_openen(bestandstypes: tuple[tuple[str, str], ...] = ()) -> Path | None:
    """Toont de native 'openen'-dialoog. Geeft None terug als de gebruiker annuleert, of als
    er geen native venster is (dan moet de aanroeper een tekstveld-fallback tonen)."""
    if not native_beschikbaar():
        return None
    import webview

    patronen = tuple(f"{label} ({patroon})" for label, patroon in bestandstypes)
    resultaat = await app.native.main_window.create_file_dialog(
        dialog_type=webview.OPEN_DIALOG, allow_multiple=False, file_types=patronen
    )
    if not resultaat:
        return None
    return Path(resultaat[0])


async def kies_bestand_opslaan(standaardnaam: str) -> Path | None:
    if not native_beschikbaar():
        return None
    import webview

    resultaat = await app.native.main_window.create_file_dialog(
        dialog_type=webview.SAVE_DIALOG, save_filename=standaardnaam
    )
    if not resultaat:
        return None
    pad = resultaat[0] if isinstance(resultaat, (list, tuple)) else resultaat
    return Path(pad)
