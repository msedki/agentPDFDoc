<# Action d'un raccourci du menu Démarrer (DIST-06) : ouvrir, arrêter, diagnostiquer ou sauvegarder l'atelier.
   Lancé depuis le dossier programme installé, avec le profil de l'utilisateur ; aucun droit administrateur. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('ouvrir', 'arreter', 'diagnostic', 'sauvegarder')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Profile,
    [switch]$NoPause
)
$ErrorActionPreference = 'Stop'
# Python écrit en UTF-8 (PYTHONUTF8) et la console le lit en UTF-8 : messages accentués intacts sous une page OEM.
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$rag = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'rag.ps1'

function Invoke-Rag([string]$Command) {
    $output = & $rag $Command -Profile $Profile | Out-String
    $code = $LASTEXITCODE
    $result = $output | ConvertFrom-Json
    if ($code -ne 0) { throw $(if ($result.message) { $result.message } else { $output.Trim() }) }
    $result
}

$failed = $false
try {
    switch ($Action) {
        'ouvrir' {
            # up est idempotent : un second clic retrouve l'instance démarrée et n'ouvre qu'une nouvelle session.
            Write-Output "Démarrage de l'atelier si nécessaire (jusqu'à deux minutes au premier lancement)…"
            Invoke-Rag 'up' | Out-Null
            Invoke-Rag 'open' | Out-Null
            Write-Output 'Atelier ouvert dans le navigateur par défaut.'
        }
        'arreter' {
            Invoke-Rag 'down' | Out-Null
            Write-Output "Atelier arrêté. Les documents, l'index et les sauvegardes sont conservés."
        }
        'diagnostic' {
            $doctor = Invoke-Rag 'doctor'
            Write-Output $doctor.verdict.summary
            foreach ($item in $doctor.verdict.rubrics) {
                Write-Output ('[{0}] {1} : {2}' -f $item.level, $item.rubric, $item.message)
                if ($item.action) { Write-Output ('        {0}' -f $item.action) }
                # Le résumé renvoie à la proposition de la rubrique (calcul GPU) : elle s'affiche sous sa rubrique.
                if ($item.proposal) { Write-Output ('        Proposition : {0}' -f $item.proposal) }
            }
        }
        'sauvegarder' {
            $backup = Invoke-Rag 'backup'
            Write-Output "Sauvegarde écrite dans $($backup.path)."
        }
    }
} catch {
    $failed = $true
    Write-Output "Échec : $($_.Exception.Message)"
}
# La fenêtre reste ouverte pour lire un échec, un diagnostic ou l'emplacement d'une sauvegarde.
if (-not $NoPause -and ($failed -or $Action -in @('diagnostic', 'sauvegarder'))) { [void](Read-Host 'Appuyez sur Entrée pour fermer') }
exit $(if ($failed) { 1 } else { 0 })
