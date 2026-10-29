# Open the current native CAD

On Windows, double-click [OPEN_CURRENT_CAD.cmd](OPEN_CURRENT_CAD.cmd) and select
the complete reference assembly or the conditional future implanted interface.
This entry works after the repository is moved to a different folder. It opens
the actual FreeCAD sources and preserves the original Stage 5 launchers.

FreeCAD **1.1 or later** is required. The launcher looks for an explicit
`SCCI_RH_FREECAD_EXE` setting, `FreeCAD.exe` on PATH, a common Windows installation,
then the verified portable installation on the original project laptop.
An invalid explicit setting produces a clear error instead of selecting a
different installation silently.

For a portable or other installation, use PowerShell:

```powershell
$env:SCCI_RH_FREECAD_EXE = 'C:\Path To FreeCAD\bin\FreeCAD.exe'
.\cad\OPEN_CURRENT_CAD.cmd -Mode reference
```

The available modes are `reference`, `reference-closed`, `future` and
`future-exploded`. With no arguments, the launcher presents a menu. To inspect
the selected executable and source path without starting an application:

```powershell
.\cad\open-current-cad.ps1 -Mode future -Probe
```

The inspection cutaway changes only display state in the current session.
The future-interface entries import the supplied editable feature module.
No source file is saved by the launcher. Opening an existing document in
FreeCAD can mark its display state as modified; retain your own unsaved work
and do not save display-only inspection changes over the released source.

The **600 x 310 x 240 mm** reference chassis contains the actual eight populated
boards at their original scale. The separate **60 x 58 x 14 mm** future package
expresses a conditional miniaturized implant and its lead interfaces. The boards
do not fit that small package. See the [Stage 5 package](stage5/README.md) for the
mechanical contracts, exchange formats and scope limits.

On other operating systems, open the reference FCStd in FreeCAD directly. For
the future interface, add `cad/stage5/future-interface` to FreeCAD's Python
module path and run the appropriate supplied FCMacro; the Windows launcher is
not a cross-platform application installer.
