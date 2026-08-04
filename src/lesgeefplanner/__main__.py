"""Entry point: start de NiceGUI-server op een vrije poort, in een native venster als
pywebview beschikbaar is (zie docs/BESLISSINGEN.md fase 2), anders in de browser."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _vrije_poort() -> int:
    """Vindt een vrije TCP-poort door te binden op poort 0 en die weer vrij te geven."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pywebview_beschikbaar() -> bool:
    try:
        import webview  # noqa: F401
    except ImportError:
        return False
    return True


def main() -> None:
    from nicegui import ui

    import lesgeefplanner.ui.app  # noqa: F401  registreert de "/" pagina
    from lesgeefplanner.ui.foutafhandeling import registreer_foutafhandeling

    registreer_foutafhandeling()

    poort = _vrije_poort()
    native = _pywebview_beschikbaar()
    ui.run(
        title="Lesgeefplanner",
        port=poort,
        reload=False,
        show=not native,
        native=native,
        window_size=(1400, 900) if native else None,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
