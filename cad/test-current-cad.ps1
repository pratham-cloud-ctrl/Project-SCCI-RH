# Probe the actual resolver in child PowerShell processes. Never execute a mock
# program or open FreeCAD. Runs with Windows PowerShell 5.1 and PowerShell 7.
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'open-current-cad.ps1'
$windowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$shellName = if ($PSEdition -eq 'Desktop') { 'powershell.exe' } elseif ($windowsHost) { 'pwsh.exe' } else { 'pwsh' }
$shell = Join-Path $PSHOME $shellName
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('scci_rh cad handoff ' + [Guid]::NewGuid().ToString('N'))
$saved = @{}
foreach ($key in @('SCCI_RH_FREECAD_EXE', 'PATH', 'ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA')) {
    $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Make-MockExecutable([string]$Path) {
    New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force | Out-Null
    [IO.File]::WriteAllText($Path, "#!/bin/sh`nexit 93`n")
    if (-not $windowsHost) { & /bin/chmod +x $Path }
}

function Probe([string]$Folder, [string]$Mode, [string]$Explicit = $null) {
    foreach ($key in @('PATH', 'ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA')) {
        [Environment]::SetEnvironmentVariable($key, $Folder, 'Process')
    }
    [Environment]::SetEnvironmentVariable('SCCI_RH_FREECAD_EXE', $Explicit, 'Process')
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $shell -NoProfile -ExecutionPolicy Bypass -File $launcher -Mode $Mode -Probe 2>&1)
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previousErrorPreference }
    return [pscustomobject]@{ Code = $code; Output = ($output -join "`n") }
}

try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    $explicitDir = Join-Path $temporary 'explicit path'
    $explicitExe = Join-Path $explicitDir 'selected FreeCAD.exe'
    Make-MockExecutable $explicitExe
    $result = Probe $explicitDir 'future' $explicitExe
    Assert-True ($result.Code -eq 0) ('Explicit executable failed: ' + $result.Output)
    $data = $result.Output | ConvertFrom-Json
    Assert-True ($data.executable -eq $explicitExe) 'The explicit executable was not selected.'
    Assert-True (-not $data.launched) 'A probe must never launch a program.'
    Assert-True ($data.target -eq (Join-Path $PSScriptRoot 'stage5/future-interface/open_future_interface.FCMacro')) 'Future source path is wrong.'

    $result = Probe $explicitDir 'reference' (Join-Path $temporary 'missing.exe')
    Assert-True ($result.Code -ne 0) 'An invalid explicit setting silently fell back.'
    Assert-True ($result.Output -match 'SCCI_RH_FREECAD_EXE does not name an existing executable') 'Missing override has no actionable explanation.'

    $pathDir = Join-Path $temporary 'path installation'
    $pathExe = Join-Path $pathDir 'FreeCAD.exe'
    Make-MockExecutable $pathExe
    $result = Probe $pathDir 'reference'
    Assert-True ($result.Code -eq 0) ('PATH discovery failed: ' + $result.Output)
    $data = $result.Output | ConvertFrom-Json
    Assert-True ($data.executable -eq $pathExe) 'PATH executable did not win before fallbacks.'
    Assert-True ($data.target -eq (Join-Path $PSScriptRoot 'stage5/open_reference_inspection.FCMacro')) 'Reference source path is wrong.'

    $commonDir = Join-Path $temporary 'common installation'
    $commonExe = Join-Path $commonDir 'FreeCAD 1.1/bin/FreeCAD.exe'
    Make-MockExecutable $commonExe
    $result = Probe $commonDir 'reference-closed'
    Assert-True ($result.Code -eq 0) ('Common installation discovery failed: ' + $result.Output)
    $data = $result.Output | ConvertFrom-Json
    Assert-True ($data.executable -eq $commonExe) 'Common installation was not selected.'
    Assert-True ($data.target -eq (Join-Path $PSScriptRoot 'stage5/SCCI_RH_stage5_reference_full.FCStd')) 'Closed source path is wrong.'

    $result = Probe $explicitDir 'future-exploded' $explicitExe
    Assert-True ($result.Code -eq 0) ('Exploded source selection failed: ' + $result.Output)
    $data = $result.Output | ConvertFrom-Json
    Assert-True ($data.target -eq (Join-Path $PSScriptRoot 'stage5/future-interface/open_future_interface_exploded.FCMacro')) 'Exploded source path is wrong.'
    Write-Host 'Passed 5 CAD handoff scenarios: explicit path with spaces, invalid override, PATH, common install, exploded selection. No application launched.'
}
finally {
    foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
    # Only this uniquely created temporary folder can be removed.
    $resolvedTemporary = [IO.Path]::GetFullPath($temporary)
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTemporary.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected temporary cleanup path.' }
    if (Test-Path -LiteralPath $resolvedTemporary) { Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force }
}
