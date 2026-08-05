@echo off
cd /d "%~dp0"
uv run lesgeefplanner
if errorlevel 1 (
    echo.
    echo Er ging iets mis bij het starten. Zie hierboven voor de foutmelding.
    pause
)
