# setup_windows.ps1 — AssurFill OCR : installation Windows
#
# Usage :
#   .\setup_windows.ps1                   installe dans ~\AssurFill (défaut)
#   .\setup_windows.ps1 -InstallDir C:\AssurFill

param(
  [string]$InstallDir = "$env:USERPROFILE\AssurFill"
)

$ErrorActionPreference = "Stop"

$RepoUrl      = "https://github.com/Nayarr/AssurFillOCR"
$VenvDir      = "$InstallDir\.venv"
$PythonVenv   = "$VenvDir\Scripts\python.exe"
$PythonVenvW  = "$VenvDir\Scripts\pythonw.exe"
$PipVenv      = "$VenvDir\Scripts\pip.exe"
$ServerScript = "$InstallDir\extension\ocr_server.py"
$TaskName     = "AssurFillOCR"

function Log   { Write-Host "[AssurFill] $args" -ForegroundColor Green }
function Warn  { Write-Host "[WARN]      $args" -ForegroundColor Yellow }
function Err   { Write-Host "[ERREUR]    $args" -ForegroundColor Red; Read-Host "`nAppuyez sur Entree pour fermer"; exit 1 }

# Attrape toutes les exceptions non gérées et les affiche avant de fermer
trap {
  Write-Host "`n[ERREUR INATTENDUE] $_" -ForegroundColor Red
  Read-Host "`nAppuyez sur Entree pour fermer"
  exit 1
}

Write-Host ""
Write-Host "  +==============================+" -ForegroundColor Cyan
Write-Host "  |  AssurFill OCR  -  Windows   |" -ForegroundColor Cyan
Write-Host "  +==============================+" -ForegroundColor Cyan
Write-Host ""

# ── Winget ────────────────────────────────────────────────────────────────────
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Err "winget introuvable. Mettez à jour Windows 10/11 (version 1709+) ou installez 'App Installer' depuis le Microsoft Store."
}

# ── 1. Git ────────────────────────────────────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Log "git non trouvé — installation via winget..."
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  # Recharger le PATH pour la session courante
  $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("PATH", "User")
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Err "L'installation de git a échoué. Installez-le manuellement depuis https://git-scm.com/download/win"
  }
  Log "git installé : $(git --version)"
}

# ── 2. Python 3.10+ ───────────────────────────────────────────────────────────
function Test-PythonOk {
  param([string]$Cmd)
  try {
    $v = & $Cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($v -match "^(\d+)\.(\d+)") {
      return ([int]$Matches[1] -eq 3) -and ([int]$Matches[2] -ge 10)
    }
  } catch {}
  return $false
}

$PythonBin = $null
foreach ($cmd in @("python", "python3")) {
  if (Test-PythonOk $cmd) { $PythonBin = $cmd; break }
}

if (-not $PythonBin) {
  Log "Python 3.10+ non trouvé — installation via winget..."
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("PATH", "User")
  foreach ($cmd in @("python", "python3")) {
    if (Test-PythonOk $cmd) { $PythonBin = $cmd; break }
  }
  if (-not $PythonBin) { Err "L'installation de Python a échoué." }
  Log "Python installé."
}
Log "Python : $(& $PythonBin --version)"

# ── 3. Cloner le dépôt ───────────────────────────────────────────────────────
if (Test-Path $InstallDir) {
  Log "Suppression du dossier existant..."
  Remove-Item -Recurse -Force $InstallDir
}
Log "Clonage dans $InstallDir..."
git clone $RepoUrl $InstallDir
if ($LASTEXITCODE -ne 0) { Err "Echec du clonage. Vérifiez votre connexion internet." }

# ── 4. Environnement virtuel ──────────────────────────────────────────────────
if (-not (Test-Path $VenvDir)) {
  Log "Création de l'environnement virtuel..."
  & $PythonBin -m venv $VenvDir
  if ($LASTEXITCODE -ne 0) { Err "Echec de la création du venv." }
}
if (-not (Test-Path $PythonVenv)) { Err "python.exe introuvable dans le venv : $PythonVenv" }

# ── 5. Dépendances ────────────────────────────────────────────────────────────
Log "Mise à jour de pip..."
& $PythonVenv -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Err "Echec de la mise à jour de pip." }

$Packages = @("flask", "opencv-python", "numpy", "paddlepaddle", "paddleocr")
foreach ($pkg in $Packages) {
  Log "Installation de $pkg..."
  & $PythonVenv -m pip install $pkg
  if ($LASTEXITCODE -ne 0) { Err "Echec de l'installation de $pkg." }
}
Log "Dépendances installées."

# ── 6. Démarrage automatique (Planificateur de tâches) ───────────────────────
Log "Enregistrement du démarrage automatique..."

$Action   = New-ScheduledTaskAction -Execute $PythonVenvW -Argument $ServerScript
$Trigger  = New-ScheduledTaskTrigger -AtLogon
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

Register-ScheduledTask `
  -TaskName  $TaskName `
  -Action    $Action `
  -Trigger   $Trigger `
  -Settings  $Settings `
  -Principal $Principal `
  -Force | Out-Null

# Démarrer immédiatement
Start-ScheduledTask -TaskName $TaskName
Log "Tâche planifiée enregistrée — démarre automatiquement à la connexion."

# ── 7. Résumé + ouverture du guide ───────────────────────────────────────────
Write-Host ""
Write-Host "  OK  Installation terminée" -ForegroundColor Green
Write-Host "  Serveur OCR  ->  http://127.0.0.1:5001"
Write-Host ""
Write-Host "  Charger l'extension Chrome :"
Write-Host "    1. chrome://extensions -> mode developpeur"
Write-Host "    2. 'Charger l'extension non empaquetee' -> $InstallDir\extension"
Write-Host ""

$HtmlGuide = "$InstallDir\install.html"
if (Test-Path $HtmlGuide) {
  Log "Ouverture du guide d'installation..."
  Start-Process $HtmlGuide
}

Read-Host "`nAppuyez sur Entree pour fermer"
