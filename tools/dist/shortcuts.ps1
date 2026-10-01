<# Raccourcis de l'atelier dans le menu Démarrer de l'utilisateur (DIST-06), sans droit administrateur.
   Crée ou remplace les quatre raccourcis du dossier du menu, qui pointent vers le programme et le profil donnés ;
   rien d'autre n'est touché. Une nouvelle version installée à côté reprend ainsi les raccourcis. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Program,
    [Parameter(Mandatory = $true)][string]$Profile,
    [string]$Menu = (Join-Path ([Environment]::GetFolderPath('Programs')) 'Atelier documentaire')
)
$ErrorActionPreference = 'Stop'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = Join-Path $Program 'tools\dist\raccourci.ps1'
if (-not (Test-Path -LiteralPath $action -PathType Leaf)) { throw "Programme incomplet : $action absent." }
$entries = [ordered]@{
    'Atelier documentaire'      = @('ouvrir', "Démarre l'atelier si nécessaire et l'ouvre dans le navigateur")
    "Arrêter l'atelier"         = @('arreter', "Arrête les services de l'atelier ; documents et index conservés")
    "Diagnostic de l'atelier"   = @('diagnostic', "Vérifie l'installation et affiche le verdict par rubrique")
    "Sauvegarder l'atelier"     = @('sauvegarder', "Sauvegarde les données de l'atelier démarré")
}
New-Item -ItemType Directory -Path $Menu -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
$created = @()
foreach ($name in $entries.Keys) {
    $path = Join-Path $Menu "$name.lnk"
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $powershell
    $link.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Action {1} -Profile "{2}"' -f $action, $entries[$name][0], $Profile
    $link.WorkingDirectory = $Program
    $link.Description = $entries[$name][1]
    $link.Save()
    $created += $path
}
[ordered]@{ status = 'created'; menu = $Menu; shortcuts = $created } | ConvertTo-Json
