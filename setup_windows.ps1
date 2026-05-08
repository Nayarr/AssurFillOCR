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
$PipVenv      = "$VenvDir\Scripts\pip.exe"
$ServerScript = "$InstallDir\extension\ocr_server.py"
$TaskName     = "AssurFillOCR"

function Log   { Write-Host "[AssurFill] $args" -ForegroundColor Green }
function Warn  { Write-Host "[WARN]      $args" -ForegroundColor Yellow }
function Err   { Write-Host "[ERREUR]    $args" -ForegroundColor Red; exit 1 }

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

# ── 3. Cloner / mettre à jour ─────────────────────────────────────────────────
if (Test-Path "$InstallDir\.git") {
  Log "Dossier existant — mise à jour du dépôt..."
  git -C $InstallDir pull --ff-only
} else {
  Log "Clonage dans $InstallDir..."
  git clone $RepoUrl $InstallDir
}

# ── 4. Environnement virtuel ──────────────────────────────────────────────────
if (-not (Test-Path $VenvDir)) {
  Log "Création de l'environnement virtuel..."
  & $PythonBin -m venv $VenvDir
}

# ── 5. Dépendances ────────────────────────────────────────────────────────────
Log "Mise à jour de pip..."
& $PipVenv install --upgrade pip --quiet

Log "Installation des paquets (peut prendre plusieurs minutes)..."
& $PipVenv install flask opencv-python numpy paddlepaddle paddleocr
Log "Dépendances installées."

# ── 6. Démarrage automatique (Planificateur de tâches) ───────────────────────
Log "Enregistrement du démarrage automatique..."

$Action   = New-ScheduledTaskAction -Execute $PythonVenv -Argument $ServerScript
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
