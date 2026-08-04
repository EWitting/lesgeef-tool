"""Startpunt voor de PyInstaller-bundel. Los van src/lesgeefplanner/__main__.py omdat die
zijn eigen sys.path-aanpassing doet voor het geval hij als los bestand gestart wordt (bv.
`python src/lesgeefplanner/__main__.py`) -- in de bevroren bundel is lesgeefplanner al
gewoon importeerbaar en is die aanpassing overbodig/onnodig."""
from lesgeefplanner.__main__ import main

if __name__ == "__main__":
    main()
