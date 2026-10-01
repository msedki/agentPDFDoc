<# Désinstallation d'une version de l'atelier (DIST-08), sans droit administrateur.
   Retire le dossier programme de cette version et les raccourcis qui pointent vers elle ; les données de l'utilisateur
   (profil, documents, index, sauvegardes) sont conservées. Une instance démarrée depuis cette version est d'abord arrêtée ;
   une instance démarrée depuis une autre version n'est pas touchée. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [string]$Menu = (Join-Path ([Environment]::GetFolderPath('Programs')) 'Atelier documentaire')
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$consoleEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$program = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$report = [ordered]@{ format = 'atelier-uninstall-v1'; started_utc = (Get-Date).ToUniversalTime().ToString('o'); program = $program; profile = $Profile }

function Test-Under([string]$Path, [string]$Folder) {
    if (-not $Path) { return $false }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\') + '\'
    return $full.StartsWith([IO.Path]::GetFullPath($Folder).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

$code = 0
try {
    # Garde : seul un dossier installé depuis un kit porte kit-manifest.json et SHA256SUMS ; le dépôt de développement non.
    foreach ($marker in 'kit-manifest.json', 'SHA256SUMS') {
        if (-not (Test-Path -LiteralPath (Join-Path $program $marker) -PathType Leaf)) {
            throw "$program n'est pas une installation de l'atelier ($marker absent) ; rien n'a été supprimé."
        }
    }
    $profilePath = [IO.Path]::GetFullPath($Profile)
    if (Test-Under $profilePath $program) { throw "Le profil $profilePath est dans le dossier programme ; rien n'a été supprimé." }
    $rag = Join-Path $program 'rag.ps1'

    # 1. Arrêt de l'instance si elle tourne depuis cette version.
    $state = & $rag status -Profile $profilePath | Out-String | ConvertFrom-Json
    $report.instance_status = $state.status
    if ($state.status -in @('starting', 'running', 'stopping') -and (Test-Under $state.supervisor.executable $program)) {
        $down = & $rag down -Profile $profilePath | Out-String | ConvertFrom-Json
        if ($down.status -notin @('stopped', 'failed')) { throw "Arrêt de l'atelier non confirmé (état $($down.status)) ; rien n'a été supprimé." }
        $report.stopped = $true
        Write-Output "[ok] arret : atelier arrêté"
    }

    # 2. Raccourcis qui pointent vers cette version ; ceux d'une autre version restent.
    $removed = @()
    if (Test-Path -LiteralPath $Menu) {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($link in Get-ChildItem -LiteralPath $Menu -Filter '*.lnk') {
            $arguments = $shell.CreateShortcut($link.FullName).Arguments
            if ($arguments -like ('*"' + (Join-Path $program 'tools\dist\raccourci.ps1') + '"*')) {
                Remove-Item -LiteralPath $link.FullName
                $removed += $link.Name
            }
        }
        if (-not (Get-ChildItem -LiteralPath $Menu -Force)) { Remove-Item -LiteralPath $Menu }
    }
    $report.shortcuts_removed = $removed
    Write-Output "[ok] raccourcis : $($removed.Count) retirés"

    # 3. Dossier programme : rmdir ne traverse pas les jonctions, il les retire sans toucher à leur cible.
    Set-Location -LiteralPath $env:TEMP
    & cmd.exe /d /c "rmdir /s /q `"$program`""
    if (Test-Path -LiteralPath $program) { throw "Dossier programme encore présent après suppression : $program (fichier ouvert par un autre programme ?)." }
    $parent = Split-Path $program -Parent
    if ((Test-Path -LiteralPath $parent) -and -not (Get-ChildItem -LiteralPath $parent -Force)) { Remove-Item -LiteralPath $parent }
    $report.status = 'uninstalled'
    Write-Output "[ok] programme : $program retiré"
    Write-Output "Données conservées : profil $profilePath et les dossiers qu'il désigne. Les supprimer reste une décision de l'utilisateur."
} catch {
    $report.status = 'failed'
    $report.error = $_.Exception.Message
    Write-Output "Désinstallation arrêtée : $($_.Exception.Message)"
    $code = 1
}
$report.finished_utc = (Get-Date).ToUniversalTime().ToString('o')
# Rapport hors des données, qui restent exactement en l'état.
$reportPath = Join-Path $env:TEMP ("atelier-uninstall-{0}.json" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Output "Rapport : $reportPath"
[Console]::OutputEncoding = $consoleEncoding
exit $code
