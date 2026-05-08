#!/usr/bin/env bash
# setup_linux.sh — AssurFill OCR : installation Linux
#
# Usage :
#   bash setup_linux.sh            installe dans ~/AssurFill (défaut)
#   bash setup_linux.sh /mon/path  installe dans le chemin indiqué

set -euo pipefail

REPO_URL="https://github.com/Nayarr/AssurFillOCR"
INSTALL_DIR="${1:-$HOME/AssurFill}"
VENV_DIR="$INSTALL_DIR/.venv"
SERVER_SCRIPT="$INSTALL_DIR/extension/ocr_server.py"
PYTHON_MIN_MINOR=10
SYSTEMD_SERVICE="assurfill-ocr"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[AssurFill]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}      $*"; }
err()  { echo -e "${RED}[ERREUR]${NC}    $*" >&2; exit 1; }

echo ""
echo "  ╔══════════════════════════════╗"
echo "  ║  AssurFill OCR  –  Linux     ║"
echo "  ╚══════════════════════════════╝"
echo ""

[ "$(uname -s)" = "Linux" ] || err "Ce script est réservé à Linux."

# ── Gestionnaire de paquets ───────────────────────────────────────────────────
_pkg() {
  if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y "$@"
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y "$@"
  elif command -v yum &>/dev/null; then
    sudo yum install -y "$@"
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm "$@"
  elif command -v zypper &>/dev/null; then
    sudo zypper install -y "$@"
  else
    err "Aucun gestionnaire de paquets reconnu. Installez $* manuellement."
  fi
}

# ── 1. Git ────────────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
  log "git non trouvé — installation en cours…"
  _pkg git
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
  log "Python 3.${PYTHON_MIN_MINOR}+ non trouvé — installation en cours…"
  _pkg python3 python3-venv python3-pip
  for cmd in python3 python; do
    _python_ok "$cmd" && PYTHON_BIN="$cmd" && break
  done
  [ -z "$PYTHON_BIN" ] && err "L'installation de Python a échoué."
  log "Python installé."
fi

# S'assurer que python3-venv est disponible (paquet séparé sur certaines distros)
if ! "$PYTHON_BIN" -m venv --help &>/dev/null 2>&1; then
  _pkg python3-venv || true
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

# ── 6. Service systemd ────────────────────────────────────────────────────────
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$SYSTEMD_SERVICE.service"
mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<UNIT
[Unit]
Description=AssurFill OCR Server
After=network.target

[Service]
ExecStart=$PYTHON_VENV $SERVER_SCRIPT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable "$SYSTEMD_SERVICE"
systemctl --user start  "$SYSTEMD_SERVICE"
log "Service systemd enregistré et démarré."

# ── 7. Résumé + ouverture du guide ───────────────────────────────────────────
echo ""
echo "  ✅  Installation terminée"
echo "  Serveur OCR  →  http://127.0.0.1:5001"
echo ""
echo "  Charger l'extension Chrome :"
echo "    1. chrome://extensions → mode développeur"
echo "    2. 'Charger l'extension non empaquetée' → $INSTALL_DIR/extension"
echo ""

if [ -f "$INSTALL_DIR/install.html" ]; then
  xdg-open "$INSTALL_DIR/install.html" 2>/dev/null || warn "Ouvrez manuellement : $INSTALL_DIR/install.html"
fi
