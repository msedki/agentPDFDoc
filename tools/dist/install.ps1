<# Installation par utilisateur depuis le kit hors ligne (DIST-03).
   Aucun droit administrateur : ni PATH, ni registre machine, ni politique d'exécution, ni service Windows.
   Le programme va dans -Destination\<version>, les données dans -DataRoot ; rien n'est remplacé. #>
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\AtelierPDF'),
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'APDF'),
    [string]$QdrantStorage,
    [string]$Ports,
    # Dossier des raccourcis : menu Démarrer de l'utilisateur ; une installation d'essai en indique un autre.
    [string]$Menu = (Join-Path ([Environment]::GetFolderPath('Programs')) 'Atelier documentaire'),
    # Mise à jour (DIST-08) : données déjà présentes ; -Previous désigne la version en place si ses raccourcis manquent.
    [switch]$Update,
    [string]$Previous,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$kit = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$report = [ordered]@{ format = 'atelier-install-v1'; started_utc = (Get-Date).ToUniversalTime().ToString('o'); kit = $kit; steps = @() }
$reportPath = $null
$switched = $false

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

function Complete-Install([int]$Code) {
    Save-Report
    [Console]::OutputEncoding = $script:consoleEncoding
    exit $Code
}

# Tout Python lancé ici écrit en UTF-8 (PYTHONUTF8, variable du seul processus d'installation, comme dans rag.ps1) et
# PowerShell 5.1 le lit en UTF-8 : sous la page OEM d'une console française, « é » arriverait sinon en « ├® ». La console
# retrouve son encodage d'origine en fin d'installation.
$env:PYTHONUTF8 = '1'
$consoleEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

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

    # 1 bis. Données déjà présentes : la nouvelle version s'installe à côté de l'actuelle, après une sauvegarde vérifiée.
    $existingProfile = Join-Path $DataRoot 'profile.yaml'
    if (Test-Path -LiteralPath $existingProfile) {
        if (-not $Update) {
            throw "Un atelier est déjà installé avec ces données ($existingProfile). Pour installer la version $($manifest.version) à côté, relancez avec -Update : sauvegarde vérifiée, puis bascule des raccourcis. Rien n'a été installé."
        }
        if (-not $Previous) {
            $link = Join-Path $Menu 'Atelier documentaire.lnk'
            if (Test-Path -LiteralPath $link) {
                $arguments = (New-Object -ComObject WScript.Shell).CreateShortcut($link).Arguments
                if ($arguments -match '-File "(.+)\\tools\\dist\\raccourci\.ps1"') { $Previous = $Matches[1] }
            }
        }
        if (-not $Previous -or -not (Test-Path -LiteralPath (Join-Path $Previous 'rag.ps1') -PathType Leaf)) {
            throw "Version installée introuvable : indiquez son dossier avec -Previous. Rien n'a été installé."
        }
        $previousRag = Join-Path $Previous 'rag.ps1'
        # La sauvegarde exige une instance démarrée ; up retrouve celle qui tourne déjà.
        $started = & $previousRag up -Profile $existingProfile | Out-String | ConvertFrom-Json
        if ($started.status -ne 'running') { throw "La version en place ne démarre pas ($($started.message)) ; sauvegarde impossible, rien n'a été installé." }
        $backup = & $previousRag backup -Profile $existingProfile | Out-String | ConvertFrom-Json
        if (-not $backup.path) { throw "Sauvegarde refusée : $($backup.message) Rien n'a été installé." }
        $verified = & $previousRag verify -Profile $existingProfile -Path $backup.path | Out-String | ConvertFrom-Json
        if ($verified.state -ne 'verified') { throw "Sauvegarde $($backup.path) non vérifiée : $($verified.message) Rien n'a été installé." }
        $stopped = & $previousRag down -Profile $existingProfile | Out-String | ConvertFrom-Json
        if ($stopped.status -notin @('stopped', 'failed')) { throw "Arrêt de la version en place non confirmé (état $($stopped.status)) ; rien n'a été installé." }
        $report.previous = $Previous
        $report.backup = $backup.path
        Write-Step 'sauvegarde' 'ok' "$($backup.path) vérifiée ; version en place ($Previous) arrêtée"
    }

    # 2. Copie vérifiée en un seul passage : chaque fichier est haché pendant sa copie (l'analyse antivirus du poste
    #    rend chaque lecture coûteuse) ; un écart retire la copie partielle. Le rapport va dans la racine des données.
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $reportPath = Join-Path $DataRoot ("install-{0}.json" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
    $kitPython = Join-Path $kit '.runtime\python\cpython-3.12.14-windows-x86_64-none\python.exe'
    # -B : le Python du kit n'écrit aucun bytecode dans le kit qu'il vérifie.
    $copy = & $kitPython -B (Join-Path $kit 'tools\dist\build_kit.py') install-copy --kit $kit --target $target | Out-String | ConvertFrom-Json
    if ($copy.status -ne 'copied') { throw "$($copy.message) Recopiez le kit ; rien n'a été installé." }
    Write-Step 'copie' 'ok' "$($copy.files) fichiers conformes à SHA256SUMS copiés dans $target"

    # 3. Environnement Python sans outils de développement, depuis le cache du kit.
    & (Join-Path $target 'bootstrap.ps1') -Offline -NoDev | Out-Null
    $python = Join-Path $target '.venv\Scripts\python.exe'
    # Précompilation de tout ce qu'importera l'exploitation (bibliothèque standard, paquets de .venv, code du projet) :
    # le dossier programme ne reçoit plus de bytecode ensuite. Quelques fichiers d'exemple des paquets ne compilent pas
    # (syntaxe d'un autre Python) : le code de sortie de compileall n'est donc pas bloquant.
    $standardLibrary = Join-Path $target '.runtime\python\cpython-3.12.14-windows-x86_64-none\Lib'
    & $python -m compileall -q -j 0 $standardLibrary (Join-Path $target '.venv\Lib\site-packages') (Join-Path $target 'services') (Join-Path $target 'tools') | Out-Null
    Write-Step 'python' 'ok' (& $python --version)

    # 4. Profil de l'utilisateur : données, stockage Qdrant court, ports libres.
    if ($report.previous) {
        # Le profil ne désigne que des données et des ports : il vaut pour la nouvelle version sans modification.
        $profilePath = $existingProfile
        Write-Step 'profil' 'ok' "$profilePath repris"
    } else {
        $profileArguments = @('init-profile', '-Target', $DataRoot)
        if ($QdrantStorage) { $profileArguments += @('-QdrantStorage', $QdrantStorage) }
        if ($Ports) { $profileArguments += @('-Ports', $Ports) }
        $created = & (Join-Path $target 'rag.ps1') @profileArguments | Out-String | ConvertFrom-Json
        if ($created.status -ne 'created') { throw "Profil non créé : $($created.message)" }
        $profilePath = $created.profile
        Write-Step 'profil' 'ok' $profilePath
    }

    # 5. Vérification, démarrage et ouverture.
    # Verdict par rubrique (vert, orange, rouge) : avant le démarrage, seule une rubrique rouge arrête l'installation.
    $doctor = & (Join-Path $target 'rag.ps1') doctor -Profile $profilePath | Out-String | ConvertFrom-Json
    $report.verdict_before_start = $doctor.verdict
    $red = @($doctor.verdict.rubrics | Where-Object { $_.level -eq 'rouge' })
    if ($red.Count) { throw ("Vérification refusée : " + (($red | ForEach-Object { "$($_.message) $($_.action)" }) -join ' ')) }
    Write-Step 'doctor' 'ok' $doctor.verdict.summary
    $shortcuts = & (Join-Path $target 'tools\dist\shortcuts.ps1') -Program $target -Profile $profilePath -Menu $Menu | Out-String | ConvertFrom-Json
    $report.shortcuts = $shortcuts.shortcuts
    $switched = $true
    Write-Step 'raccourcis' 'ok' "$(@($shortcuts.shortcuts).Count) raccourcis dans $($shortcuts.menu)"
    if (-not $NoStart) {
        $up = & (Join-Path $target 'rag.ps1') up -Profile $profilePath | Out-String | ConvertFrom-Json
        if ($up.status -ne 'running') { throw "Démarrage refusé : $($up.message)" }
        Write-Step 'demarrage' 'ok' $up.instance_id
        $doctor = & (Join-Path $target 'rag.ps1') doctor -Profile $profilePath | Out-String | ConvertFrom-Json
        $report.verdict = $doctor.verdict
        foreach ($item in $doctor.verdict.rubrics) { Write-Output ("  [{0}] {1} : {2}" -f $item.level, $item.rubric, $item.message) }
        Write-Step 'verdict' $doctor.verdict.level $doctor.verdict.summary
        # Contrôle réel dans une racine et des ports temporaires : import, extraction, recherche, provenance, réponse si admise.
        $control = & (Join-Path $target 'rag.ps1') selftest -Profile $profilePath | Out-String | ConvertFrom-Json
        $report.selftest = $control
        foreach ($item in $control.steps) { Write-Output ("  [{0}] {1} : {2}" -f $item.status, $item.step, $item.detail) }
        if ($control.level -eq 'rouge') { throw "$($control.summary) Le programme est installé ; « Diagnostic de l'atelier » et le rapport d'installation détaillent l'échec." }
        Write-Step 'controle' $control.level $control.summary
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
    if ($report.previous -and -not $switched) {
        Write-Output "La version précédente ($($report.previous)) reste installée avec ses raccourcis ; relancez-la par « Atelier documentaire ». Sauvegarde conservée : $($report.backup)."
    } elseif ($report.previous) {
        Write-Output "Retour à la version précédente : & '$($report.previous)\tools\dist\shortcuts.ps1' -Program '$($report.previous)' -Profile '$existingProfile', puis, si la nouvelle version a déjà démarré sur ces données, restauration de $($report.backup) dans une racine neuve (.\rag.ps1 restore)."
    }
    Complete-Install 1
}
Complete-Install 0
