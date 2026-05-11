#!/bin/bash
# setup_macos.sh — AssurFill OCR : installation macOS
#
# Usage :
#   bash setup_macos.sh               installe dans ~/AssurFillOCR (défaut)
#   bash setup_macos.sh /mon/path     installe dans le chemin indiqué

set -euo pipefail

REPO_URL="https://github.com/Nayarr/AssurFillOCR"
INSTALL_DIR="${1:-$HOME/AssurFillOCR}"
VENV_DIR="$INSTALL_DIR/.venv"
SERVER_SCRIPT="$INSTALL_DIR/extension/ocr_server.py"
PYTHON_MIN_MINOR=10
SERVICE_NAME="com.assurfill.ocr"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[AssurFill]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}      $*"; }
err()  { echo -e "${RED}[ERREUR]${NC}    $*" >&2; exit 1; }

echo ""
echo "  ╔══════════════════════════════╗"
echo "  ║  AssurFill OCR  –  macOS     ║"
echo "  ╚══════════════════════════════╝"
echo ""

[ "$(uname -s)" = "Darwin" ] || err "Ce script est réservé à macOS."

# ── Homebrew ──────────────────────────────────────────────────────────────────
_ensure_brew() {
  if ! command -v brew &>/dev/null; then
    log "Homebrew non trouvé — installation en cours…"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -f /opt/homebrew/bin/brew ]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f /usr/local/bin/brew ]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
    command -v brew &>/dev/null || err "L'installation de Homebrew a échoué."
    log "Homebrew installé."
  fi
}

# ── 1. Git ────────────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
  log "git non trouvé — installation via Homebrew…"
  _ensure_brew
  brew install git
  command -v git &>/dev/null || err "L'installation de git a échoué."
  log "git installé : $(git --version)"
fi

# ── 2. Python 3.10+ ───────────────────────────────────────────────────────────
_python_ok() {
  command -v "$1" &>/dev/null || return 1
  local maj min
  maj=$("$1" -c "import sys; print(sys.version_info.major)" 2>/dev/null) || return 1
  min=$("$1" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || return 1
  [ "$maj" -eq 3 ] && [ "$min" -ge "$PYTHON_MIN_MINOR" ]
}

PYTHON_BIN=""
for cmd in python3 python; do
  _python_ok "$cmd" && PYTHON_BIN="$cmd" && break
done

if [ -z "$PYTHON_BIN" ]; then
  log "Python 3.${PYTHON_MIN_MINOR}+ non trouvé — installation via Homebrew…"
  _ensure_brew
  brew install python@3.12
  for candidate in \
      "$(brew --prefix python@3.12)/bin/python3.12" \
      "$(brew --prefix)/bin/python3.12" \
      python3.12 python3; do
    _python_ok "$candidate" 2>/dev/null && PYTHON_BIN="$candidate" && break
  done
  [ -z "$PYTHON_BIN" ] && err "L'installation de Python a échoué."
  log "Python installé."
fi
log "Python : $("$PYTHON_BIN" --version)"

# ── 3. Cloner / mettre à jour ─────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  log "Dossier existant — mise à jour du dépôt…"
  git -C "$INSTALL_DIR" pull --ff-only
else
  log "Clonage dans $INSTALL_DIR…"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── 4. Environnement virtuel ──────────────────────────────────────────────────
[ ! -d "$VENV_DIR" ] && "$PYTHON_BIN" -m venv "$VENV_DIR" && log "Environnement virtuel créé."
PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

# ── 5. Dépendances ────────────────────────────────────────────────────────────
log "Mise à jour de pip…"
"$PIP" install --upgrade pip --quiet
log "Installation des paquets (peut prendre plusieurs minutes)…"
"$PIP" install flask opencv-python numpy paddlepaddle paddleocr
log "Dépendances installées."

# ── 6. Service launchd ────────────────────────────────────────────────────────
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/$SERVICE_NAME.plist"
LOG_FILE="$HOME/Library/Logs/assurfill-ocr.log"
mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$SERVICE_NAME</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_VENV</string>
    <string>$SERVER_SCRIPT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$LOG_FILE</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load   "$PLIST_FILE"
log "Service launchd enregistré — démarre automatiquement à la connexion."
log "Logs : $LOG_FILE"

# ── 7. Résumé + ouverture du guide ───────────────────────────────────────────
echo ""
echo "  ✅  Installation terminée"
echo "  Serveur OCR  →  http://127.0.0.1:5001"
echo ""
echo "  Charger l'extension Chrome :"
echo "    1. chrome://extensions → mode développeur"
echo "    2. 'Charger l'extension non empaquetée' → $INSTALL_DIR/extension"
echo ""

[ -f "$INSTALL_DIR/install.html" ] && open "$INSTALL_DIR/install.html"
