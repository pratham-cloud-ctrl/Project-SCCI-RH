@echo off
setlocal
set "SCCI_RH_KICAD=E:\project workspace assests\EDA\KiCAD\bin\kicad.exe"
if not exist "%SCCI_RH_KICAD%" (
  echo The configured KiCad executable was not found.
  echo Open current_driver.kicad_pro from your KiCad installation.
  exit /b 1
)
start "" "%SCCI_RH_KICAD%" "%~dp0current_driver.kicad_pro"
