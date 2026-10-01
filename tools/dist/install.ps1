<# Installation par utilisateur depuis le kit hors ligne (DIST-03).
   Aucun droit administrateur : ni PATH, ni registre machine, ni politique d'exécution, ni service Windows.
   Le programme va dans -Destination\<version>, les données dans -DataRoot ; rien n'est remplacé. #>
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\AtelierPDF'),
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'APDF'),
    [string]$QdrantStorage,
    [string]$Ports,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$kit = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$report = [ordered]@{ format = 'atelier-install-v1'; started_utc = (Get-Date).ToUniversalTime().ToString('o'); kit = $kit; steps = @() }
$reportPath = $null

function Write-Step([string]$Name, [string]$Status, [string]$Detail) {
    $script:report.steps += [ordered]@{ step = $Name; status = $Status; detail = $Detail; at_utc = (Get-Date).ToUniversalTime().ToString('o') }
    Write-Output ("[{0}] {1} {2}" -f $Status, $Name, $Detail)
}

function Save-Report {
    if ($script:reportPath) {
        $script:report.finished_utc = (Get-Date).ToUniversalTime().ToString('o')
        $script:report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $script:reportPath -Encoding UTF8
    }
}

try {
    # 1. Prérequis, sans rien modifier.
    $manifest = Get-Content -LiteralPath (Join-Path $kit 'kit-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $os = Get-CimInstance Win32_OperatingSystem
    if (-not [Environment]::Is64BitOperatingSystem -or [int]$os.BuildNumber -lt 22000) {
        throw "Ce poste n'est pas un Windows 11 64 bits (build $($os.BuildNumber)). Installation arrêtée, aucun fichier copié."
    }
    $memoryGib = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    if ($memoryGib -lt 15) { throw "Ce poste a $memoryGib Gio de mémoire physique ; l'atelier en demande 16. Installation arrêtée, aucun fichier copié." }
    $target = Join-Path $Destination $manifest.version
    if (Test-Path -LiteralPath $target) { throw "La version $($manifest.version) est déjà installée dans $target ; rien n'a été remplacé." }
    $drive = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Destination))
    $free = (Get-PSDrive -Name $drive.Substring(0, 1)).Free
    $needed = [long]$manifest.bytes + 3GB
    if ($free -lt $needed) { throw ("Espace insuffisant sur {0} : {1:N1} Gio libres, {2:N1} Gio nécessaires." -f $drive, ($free / 1GB), ($needed / 1GB)) }
    Write-Step 'prerequis' 'ok' ("Windows build {0}, {1} Gio de mémoire, {2:N1} Gio libres" -f $os.BuildNumber, $memoryGib, ($free / 1GB))

    # 2. Intégrité du kit avec le Python qu'il contient.
    $kitPython = Join-Path $kit '.runtime\python\cpython-3.12.14-windows-x86_64-none\python.exe'
    $verification = & $kitPython (Join-Path $kit 'tools\dist\build_kit.py') verify --kit $kit | Out-String | ConvertFrom-Json
    if ($verification.status -ne 'verified') {
        $first = @($verification.altered_or_missing + $verification.unexpected)[0]
        throw "Kit altéré ou incomplet (par exemple $first). Recopiez le kit ; rien n'a été installé."
    }
    Write-Step 'integrite' 'ok' "$($verification.files) fichiers conformes à SHA256SUMS"

    # 3. Copie du programme ; le rapport va dans la racine des données.
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $reportPath = Join-Path $DataRoot ("install-{0}.json" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
    New-Item -ItemType Directory -Path $target | Out-Null
    Copy-Item -Path (Join-Path $kit '*') -Destination $target -Recurse
    Write-Step 'copie' 'ok' $target

    # 4. Environnement Python sans outils de développement, depuis le cache du kit.
    & (Join-Path $target 'bootstrap.ps1') -Offline -NoDev | Out-Null
    $python = Join-Path $target '.venv\Scripts\python.exe'
    # Précompilation : le programme n'écrira plus de bytecode pendant l'exploitation.
    & $python -m compileall -q (Join-Path $target 'services') (Join-Path $target 'tools') | Out-Null
    Write-Step 'python' 'ok' (& $python --version)

    # 5. Profil de l'utilisateur : données, stockage Qdrant court, ports libres.
    $profileArguments = @('init-profile', '-Target', $DataRoot)
    if ($QdrantStorage) { $profileArguments += @('-QdrantStorage', $QdrantStorage) }
    if ($Ports) { $profileArguments += @('-Ports', $Ports) }
    $created = & (Join-Path $target 'rag.ps1') @profileArguments | Out-String | ConvertFrom-Json
    if ($created.status -ne 'created') { throw "Profil non créé : $($created.message)" }
    $profilePath = $created.profile
    Write-Step 'profil' 'ok' $profilePath

    # 6. Vérification, démarrage et ouverture.
    $doctor = & (Join-Path $target 'rag.ps1') doctor -Profile $profilePath | Out-String | ConvertFrom-Json
    $report.doctor_api_ready = $doctor.services.api_ready
    Write-Step 'doctor' 'ok' 'rapport joint'
    if (-not $NoStart) {
        $up = & (Join-Path $target 'rag.ps1') up -Profile $profilePath | Out-String | ConvertFrom-Json
        if ($up.status -ne 'running') { throw "Démarrage refusé : $($up.message)" }
        Write-Step 'demarrage' 'ok' $up.instance_id
        & (Join-Path $target 'rag.ps1') open -Profile $profilePath | Out-Null
        Write-Step 'ouverture' 'ok' "atelier ouvert dans le navigateur par défaut"
    }
    $report.status = 'installed'
    $report.program = $target
    $report.profile = $profilePath
    Write-Output "Installation terminée. Profil : $profilePath. Rapport : $reportPath"
} catch {
    $report.status = 'failed'
    $report.error = $_.Exception.Message
    Write-Output "Installation arrêtée : $($_.Exception.Message)"
    Save-Report
    exit 1
}
Save-Report
exit 0
