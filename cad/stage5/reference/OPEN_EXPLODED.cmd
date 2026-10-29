@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0extract_steps.ps1"
if errorlevel 1 (
 pause
 exit /b 1
)
if not defined SCCI_RH_FREECAD_EXE set "SCCI_RH_FREECAD_EXE=E:\project workspace assests\CAD\FreeCAD\bin\FreeCAD.exe"
if not exist "%SCCI_RH_FREECAD_EXE%" (
 echo Set SCCI_RH_FREECAD_EXE to your FreeCAD executable.
 pause
 exit /b 1
)
start "" "%SCCI_RH_FREECAD_EXE%" "%~dp0extracted\SCCI_RH_reference_exploded.step"
