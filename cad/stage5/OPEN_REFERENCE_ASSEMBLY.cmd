@echo off
set "SCCI_RH_FREECAD=E:\project workspace assests\CAD\FreeCAD\bin\FreeCAD.exe"
if not exist "%SCCI_RH_FREECAD%" (
  echo FreeCAD was not found at the configured laptop path.
  echo Open SCCI_RH_stage5_reference_full.FCStd with FreeCAD 1.1 or later.
  pause
  exit /b 1
)
start "" "%SCCI_RH_FREECAD%" "%~dp0open_reference_inspection.FCMacro"
