#!/usr/bin/env bash
# ============================================================
#  Student Finance - one-command start for Linux / macOS
#  Usage:  bash run.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.11+ is required (python3 not found)."; exit 1; }

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/5] Creating virtual environment..."
  "$PY" -m venv .venv
fi

echo "[2/5] Installing requirements (first run takes a few minutes)..."
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example ..."
  cp .env.example .env
fi

echo "[3/5] Applying database migrations..."
.venv/bin/python manage.py migrate --noinput

echo "[4/5] Creating demo account with synthetic data (skipped if it exists)..."
.venv/bin/python manage.py seed_demo --keep

echo
echo "[5/5] Starting server..."
echo "------------------------------------------------------------"
echo "  Open:  http://127.0.0.1:8000"
echo "  Demo:  username demo   password DemoPass2026!"
echo "  Stop:  press CTRL+C"
echo "------------------------------------------------------------"
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
