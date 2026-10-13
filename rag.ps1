<# Entrée Windows native. Les effets réseau sont limités à provision/pull-model. #>
[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('provision','doctor','up','open','status','logs','down','pull-model','backup','restore','verify','init-profile','selftest')]
    [string]$Command = 'doctor',
    [string]$Profile,
    [string]$Model,
    [string]$Only,
    [switch]$Offline,
    [switch]$SkipModel,
    [string]$Path,
    [string]$Target,
    [string]$Report,
    [string]$QdrantStorage,
    [string]$Ports,
    [long]$MemoryTotalBytes,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython -PathType Leaf)) {
    throw 'Environnement isolé absent. Exécuter bootstrap.ps1 pour préparer uv et Python3.12, puis rag.ps1 provision.'
}
$resolvedProfile = if (-not $Profile) { $null } elseif ([System.IO.Path]::IsPathRooted($Profile)) {
    [System.IO.Path]::GetFullPath($Profile)
} else {
    Join-Path $projectRoot $Profile
}
$arguments = @('-B','-m','services.runtime.cli',$Command)
if ($PSBoundParameters.ContainsKey('Profile')) { $arguments += @('--profile',$resolvedProfile) }
if ($Model) { $arguments += @('--model',$Model) }
if ($Only) { $arguments += @('--only',$Only) }
if ($Offline) { $arguments += '--offline' }
if ($SkipModel) { $arguments += '--skip-model' }
if ($Path) { $arguments += @('--path',$Path) }
if ($Target) { $arguments += @('--target',$Target) }
if ($Report) { $arguments += @('--report',$Report) }
if ($QdrantStorage) { $arguments += @('--qdrant-storage',$QdrantStorage) }
if ($Ports) { $arguments += @('--ports',$Ports) }
if ($PSBoundParameters.ContainsKey('MemoryTotalBytes')) { $arguments += @('--memory-total-bytes',[string]$MemoryTotalBytes) }
if ($NoBrowser) { $arguments += '--no-browser' }
$env:PYTHONUTF8 = '1'
Push-Location -LiteralPath $projectRoot
try {
    & $projectPython @arguments
    $resultCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $resultCode
