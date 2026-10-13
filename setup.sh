#!/usr/bin/env bash
# Einmal-Setup auf dem Mac: venv + Pakete + Jupyter-Kernel + git-Repo.
# Aufruf im Projektordner:  bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"

# 1) Python >= 3.10 finden (bevorzugt 3.12 – damit wurden die Notebooks erstellt)
PY=""
for c in python3.12 python3.11 python3.13 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "FEHLER: Kein Python >= 3.10 gefunden (macOS-System-Python ist 3.9)."
  echo "        Installieren z. B. mit:  brew install python@3.12"
  exit 1
fi
echo ">> Verwende $("$PY" --version) aus $(command -v "$PY")"

# 2) Virtuelle Umgebung
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip freeze > requirements.lock.txt

# 3) Jupyter-Kernel registrieren (in VS Code / JupyterLab auswählbar)
python -m ipykernel install --user --name ai-agents-oreilly --display-name "Python (AI Agents O'Reilly)"

# 4) .env aus Vorlage
[ -f .env ] || { cp .env.example .env; echo ">> .env angelegt – bitte API-Keys eintragen."; }

# 5) git
if [ ! -d .git ]; then
  git init -b main
fi
if [ -z "$(git config user.name || true)" ] || [ -z "$(git config user.email || true)" ]; then
  echo "HINWEIS: git user.name/user.email nicht gesetzt – erst setzen, dann:"
  echo "         git add -A && git commit -m 'Initialer Stand: Kurs-Notebooks + Setup'"
  exit 0
fi
git add -A
if git diff --cached --quiet; then
  echo ">> Nichts zu committen."
else
  git commit -m "Initialer Stand: Kurs-Notebooks Level 2–4 + Python-Setup"
fi
echo ">> Fertig. Aktivieren mit:  source .venv/bin/activate"
