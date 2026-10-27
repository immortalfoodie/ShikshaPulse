# ShikshaPulse one-command start (Windows PowerShell). First run installs everything.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python environment..."
    python -m venv .venv
    .\.venv\Scripts\pip install --default-timeout=120 -r requirements.txt
}
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path "dist")) { npm run build }
Set-Location "$root\backend"
Write-Host "ShikshaPulse running at http://localhost:8000  (first start generates demo data ~30s)"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
