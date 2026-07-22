@echo off
setlocal
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem Otzaria Icons - build helper launcher (Windows).
rem Double-click this file to open the graphical build menu.
rem It launches otzaria_build.py with a windowed Python interpreter so no
rem console window stays open. Prefers pythonw, then the "py" launcher, then
rem plain python as a last resort.
rem ---------------------------------------------------------------------------

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0otzaria_build.py"
    goto :eof
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" py -w "%~dp0otzaria_build.py"
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "" python "%~dp0otzaria_build.py"
    goto :eof
)

echo Python was not found on PATH.
echo Install Python 3 from https://www.python.org/downloads/ (tick "Add to PATH"),
echo then double-click this file again.
pause
