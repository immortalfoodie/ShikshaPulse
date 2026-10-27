#!/usr/bin/env bash
# ShikshaPulse one-command start (macOS/Linux/Git Bash). First run installs everything.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
PY=python3; command -v python3 >/dev/null || PY=python
if [ ! -d .venv ]; then $PY -m venv .venv; fi
if [ -f .venv/Scripts/python ]; then VPY=.venv/Scripts/python; else VPY=.venv/bin/python; fi
$VPY -m pip install -q --default-timeout=120 -r requirements.txt
[ -f .env ] || cp .env.example .env
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
[ -d dist ] || npm run build
cd "$ROOT/backend"
echo "ShikshaPulse running at http://localhost:8000  (first start generates demo data ~30s)"
PYTHONIOENCODING=utf-8 $VPY -m uvicorn app.main:app --port 8000
