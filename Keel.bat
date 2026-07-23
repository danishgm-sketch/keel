@echo off
rem  Double-click to open Keel. First run installs it; after that it just opens.
cd /d "%~dp0"

python -c "import keel" 1>nul 2>nul
if errorlevel 1 (
    echo First run - installing Keel, this takes a minute...
    python -m pip install -e ".[desktop]"
    if errorlevel 1 (
        echo.
        echo Could not install. Make sure Python 3.11+ is installed and on PATH.
        pause
        exit /b 1
    )
)

rem  pythonw = no console window; the Keel app window opens on its own.
start "" pythonw -m keel app --dir data
exit
