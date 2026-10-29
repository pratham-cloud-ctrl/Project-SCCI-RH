@echo off
setlocal
if not defined SCCI_RH_KICAD_BIN set "SCCI_RH_KICAD_BIN=E:\project workspace assests\EDA\KiCAD\bin"
if not exist "%SCCI_RH_KICAD_BIN%\kicad.exe" (
  echo Set SCCI_RH_KICAD_BIN to your KiCad 10 bin directory.
  pause
  exit /b 1
)
start "" "%SCCI_RH_KICAD_BIN%\kicad.exe" "%~dp0integration\master\SCCI_RH_integrated.kicad_pro"
