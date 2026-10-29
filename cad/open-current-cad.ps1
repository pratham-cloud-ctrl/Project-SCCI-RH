param(
    [ValidateSet('menu', 'reference', 'reference-closed', 'future', 'future-exploded')]
    [string]$Mode = 'menu',
    [switch]$Probe
)

$ErrorActionPreference = 'Stop'

function Resolve-FreeCAD {
    if ($env:SCCI_RH_FREECAD_EXE) {
        if (-not (Test-Path -LiteralPath $env:SCCI_RH_FREECAD_EXE -PathType Leaf)) {
            throw 'SCCI_RH_FREECAD_EXE does not name an existing executable. Set it to the full path of FreeCAD.exe, without extra quotation marks.'
        }
        return (Resolve-Path -LiteralPath $env:SCCI_RH_FREECAD_EXE).ProviderPath
    }

    $command = Get-Command FreeCAD.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }

    $candidates = @()
    $localPrograms = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs' } else { $null }
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA, $localPrograms)) {
        if (-not $base -or -not (Test-Path -LiteralPath $base -PathType Container)) { continue }
        $installs = Get-ChildItem -LiteralPath $base -Directory -Filter 'FreeCAD*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
        foreach ($install in $installs) {
            $candidates += Join-Path $install.FullName 'bin\FreeCAD.exe'
        }
    }
    # This laptop's verified portable installation is the final fallback.
    $candidates += 'E:\project workspace assests\CAD\FreeCAD\bin\FreeCAD.exe'
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).ProviderPath
        }
    }
    throw 'FreeCAD was not found. Install FreeCAD 1.1 or later, then set SCCI_RH_FREECAD_EXE to the full path of FreeCAD.exe. See cad\CURRENT_CAD.md.'
}

try {
    if ($Mode -eq 'menu') {
        if ($Probe) { $Mode = 'reference' }
        else {
            Write-Host 'Project SCCI RH - native CAD'
            Write-Host '1. Complete eight-board reference assembly (inspection cutaway)'
            Write-Host '2. Complete reference assembly (saved closed view)'
            Write-Host '3. Conditional future implanted interface'
            Write-Host '4. Conditional future interface (exploded view)'
            $choice = Read-Host 'Select 1-4, or press Enter for 1'
            $Mode = switch ($choice) {
                '' { 'reference' }
                '1' { 'reference' }
                '2' { 'reference-closed' }
                '3' { 'future' }
                '4' { 'future-exploded' }
                default { throw 'Select 1, 2, 3 or 4.' }
            }
        }
    }

    $target = switch ($Mode) {
        'reference' { Join-Path $PSScriptRoot 'stage5\open_reference_inspection.FCMacro' }
        'reference-closed' { Join-Path $PSScriptRoot 'stage5\SCCI_RH_stage5_reference_full.FCStd' }
        'future' { Join-Path $PSScriptRoot 'stage5\future-interface\open_future_interface.FCMacro' }
        'future-exploded' { Join-Path $PSScriptRoot 'stage5\future-interface\open_future_interface_exploded.FCMacro' }
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "The selected CAD entry is missing: $target. Extract or clone the complete repository before opening it."
    }
    $executable = Resolve-FreeCAD
    if ($Probe) {
        [ordered]@{ mode = $Mode; executable = $executable; target = $target; launched = $false } | ConvertTo-Json
        exit 0
    }

    # The supplied feature module is needed for the future model's editable history.
    $featurePath = Join-Path $PSScriptRoot 'stage5\future-interface'
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$featurePath;$env:PYTHONPATH" } else { $featurePath }
    # This is the user's interactive CAD viewer, so its window must be visible.
    Start-Process -FilePath $executable -ArgumentList ('"' + $target + '"') -WindowStyle Normal
    Write-Host "Opened $Mode with $executable"
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
