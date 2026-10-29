@echo off
setlocal
set "SCCI_RH_KICAD=E:\project workspace assests\EDA\KiCAD\bin\kicad.exe"
if not exist "%SCCI_RH_KICAD%" (
  echo KiCad was not found at the configured installation path.
  echo Open contact_router.kicad_pro from your KiCad installation.
  pause
  exit /b 1
)
start "" "%SCCI_RH_KICAD%" "%~dp0contact_router.kicad_pro"
endlocal
