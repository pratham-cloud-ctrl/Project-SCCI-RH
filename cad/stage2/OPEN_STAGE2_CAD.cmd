@echo off
set "SCCI_RH_STAGE2_FREECAD=E:\project workspace assests\CAD\FreeCAD\bin\FreeCAD.exe"
if not exist "%SCCI_RH_STAGE2_FREECAD%" (
  echo Set SCCI_RH_STAGE2_FREECAD in this launcher to your FreeCAD executable.
  pause
  exit /b 1
)
start "" "%SCCI_RH_STAGE2_FREECAD%" "%~dp0SCCI_RH_stage2_allocation.FCStd"
