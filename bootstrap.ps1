<# Provision uv/Python dans le projet ; aucune modification de PATH ou ExecutionPolicy. #>
[CmdletBinding()]
param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$bootstrapRoot = Join-Path $projectRoot '.runtime/bootstrap'
$uvPath = Join-Path $bootstrapRoot 'bin/uv.exe'
if (-not (Test-Path -LiteralPath $uvPath -PathType Leaf)) {
    if ($Offline) { throw 'uv local absent du kit offline.' }
    $archivePath = Join-Path $bootstrapRoot 'uv-0.12.21-windows.zip'
    New-Item -ItemType Directory -Path $bootstrapRoot -Force | Out-Null
    $uri = 'https://github.com/astral-sh/uv/releases/download/0.12.21/uv-x86_64-pc-windows-msvc.zip'
    Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $archivePath
    $digest = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($digest -ne '5d223efa0bf00208c3853246af09420419dfbd352536aa6bb8163d6170e23890') {
        throw 'Archive officielle uv : SHA-256 non conforme, aucune exécution.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        foreach ($name in @('uv.exe','uvx.exe','uvw.exe')) {
            $entry = @($archive.Entries | Where-Object { $_.Name -eq $name })
            if ($entry.Count -gt 1) { throw 'Archive uv ambiguë.' }
            if ($entry.Count -eq 1) {
                $binDirectory = Join-Path $bootstrapRoot 'bin'
                New-Item -ItemType Directory -Path $binDirectory -Force | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry[0],(Join-Path $binDirectory $name),$true)
            }
        }
    } finally { $archive.Dispose() }
}
$version = & $uvPath --version
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^uv 0\.12\.21\b') { throw 'Version uv différente du verrou.' }
$managedPythonRoot = Join-Path $projectRoot '.runtime/python'
$cacheDirectory = Join-Path $projectRoot '.runtime/cache/uv'
$managedPython = Join-Path $managedPythonRoot 'cpython-3.12.14-windows-x86_64-none/python.exe'
$uvOptions = @('--cache-dir',$cacheDirectory)
if ($Offline) { $uvOptions += '--offline' }
if (-not (Test-Path -LiteralPath $managedPython -PathType Leaf)) {
    & $uvPath python install 3.12.14 --install-dir $managedPythonRoot --no-bin --no-registry @uvOptions
    if ($LASTEXITCODE -ne 0) { throw 'Installation Python isolé échouée.' }
}
Push-Location -LiteralPath $projectRoot
try {
    & $uvPath sync --locked --python $managedPython --no-python-downloads @uvOptions
    if ($LASTEXITCODE -ne 0) { throw 'Synchronisation Python verrouillée échouée.' }
} finally { Pop-Location }
Write-Output 'Environnement Python isolé prêt. Exécuter .\rag.ps1 provision pour artefacts et modèle.'
