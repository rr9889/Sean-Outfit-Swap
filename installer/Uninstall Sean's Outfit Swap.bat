@echo off
rem Sean's Outfit Swap - uninstall.  Optional argument: the game folder.
setlocal
cd /d "%~dp0"
set "GAME=%~1"
if "%GAME%"=="" set "GAME=C:\Saboteur\The Saboteur"
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3 outfit_swap.py uninstall --game "%GAME%"
) else (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    python outfit_swap.py uninstall --game "%GAME%"
  ) else (
    echo.
    echo Python 3 was not found.  Install Python 3.8 or newer from https://www.python.org/downloads/
  )
)
echo.
pause
