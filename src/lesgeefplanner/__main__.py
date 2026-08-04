"""Entry point: start de NiceGUI-server op een vrije poort en open de browser."""
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


def main() -> None:
    from nicegui import ui

    import lesgeefplanner.ui.app  # noqa: F401  registreert de "/" pagina

    poort = _vrije_poort()
    ui.run(title="Lesgeefplanner", port=poort, reload=False, show=True, native=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
