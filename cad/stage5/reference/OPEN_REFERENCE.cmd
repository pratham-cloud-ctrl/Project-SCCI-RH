@echo off
setlocal
if not defined SCCI_RH_FREECAD_EXE set "SCCI_RH_FREECAD_EXE=E:\project workspace assests\CAD\FreeCAD\bin\FreeCAD.exe"
if not exist "%SCCI_RH_FREECAD_EXE%" (
 echo Set SCCI_RH_FREECAD_EXE to your FreeCAD executable.
 pause
 exit /b 1
)
start "" "%SCCI_RH_FREECAD_EXE%" "%~dp0SCCI_RH_reference_assembly.FCStd"
