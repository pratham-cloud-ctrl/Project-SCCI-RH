[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$receipt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'producer-geometry.json') -Raw | ConvertFrom-Json
$destination = Join-Path $PSScriptRoot 'extracted'
[System.IO.Directory]::CreateDirectory($destination) | Out-Null
foreach ($memberName in @('SCCI_RH_reference_assembly.step','SCCI_RH_reference_exploded.step')) {
    $binding = $receipt.outputs.$memberName
    $archivePath = Join-Path $PSScriptRoot $binding.lossless_archive
    if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $binding.archive_sha256) {
        throw "Archive checksum mismatch: $archivePath"
    }
    $targetPath = Join-Path $destination $memberName
    if (Test-Path -LiteralPath $targetPath) {
        if ((Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $binding.sha256) { continue }
        throw "An existing extracted file has a different checksum. Rename it before extracting: $targetPath"
    }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        if ($archive.Entries.Count -ne 1 -or $archive.Entries[0].FullName -ne $memberName) { throw 'Unexpected archive member list' }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($archive.Entries[0],$targetPath,$false)
    } finally { $archive.Dispose() }
    if ((Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $binding.sha256) { throw "Extracted checksum mismatch: $targetPath" }
}
Write-Host "Verified populated STEP models are in $destination"
