# ForgeOS — one-command setup + start (Windows PowerShell).
#
#   .\start.ps1
#
# Path A (preferred): Docker Desktop is installed -> builds and runs
# backend, background worker, and frontend in containers.
# Path B (fallback): no Docker -> sets up a local Python venv +
# node_modules and runs backend/worker/frontend as three background
# jobs.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

New-Item -ItemType Directory -Force -Path "storage" | Out-Null

if (-not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "Created backend\.env (defaults: `$0 offline mode, AI_PROVIDER=mock)"
}
if (-not (Test-Path "frontend\.env.local")) {
    Copy-Item "frontend\.env.local.example" "frontend\.env.local"
    Write-Host "Created frontend\.env.local"
}

$dockerOk = $false
try {
    docker compose version | Out-Null
    $dockerOk = $true
} catch { $dockerOk = $false }

if ($dockerOk) {
    Write-Host "Docker detected - building and starting ForgeOS in containers..."
    Write-Host "  Backend:  http://localhost:8000  (docs at /docs)"
    Write-Host "  Frontend: http://localhost:3000"
    docker compose up --build
    exit
}

Write-Host "Docker not found - falling back to a native local setup."
Write-Host "(Install Docker Desktop for the simpler one-command path next time: https://docker.com)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.10+ is required." }
if (-not (Get-Command node -ErrorAction SilentlyContinue))   { throw "Node.js 18+ is required." }

if (-not (Test-Path "backend\.venv")) {
    Write-Host "Creating backend virtual environment..."
    python -m venv backend\.venv
}
& backend\.venv\Scripts\pip.exe install --quiet --upgrade pip
& backend\.venv\Scripts\pip.exe install --quiet -r backend\requirements.txt

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies (npm install)..."
    Push-Location frontend
    npm install
    Pop-Location
}

New-Item -ItemType Directory -Force -Path "logs" | Out-Null

Write-Host "Starting backend  (http://localhost:8000, docs at /docs)"
Start-Job -Name forgeos-backend -ScriptBlock {
    Set-Location "$using:PSScriptRoot\backend"
    & .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
} | Out-Null

Start-Sleep -Seconds 2

Write-Host "Starting background worker (30 min cycle)"
Start-Job -Name forgeos-worker -ScriptBlock {
    Set-Location "$using:PSScriptRoot\backend"
    & .\.venv\Scripts\python.exe worker.py 1800
} | Out-Null

Write-Host "Starting frontend (http://localhost:3000)"
Start-Job -Name forgeos-frontend -ScriptBlock {
    Set-Location "$using:PSScriptRoot\frontend"
    npm run dev
} | Out-Null

Write-Host ""
Write-Host "ForgeOS is up. Jobs: forgeos-backend, forgeos-worker, forgeos-frontend"
Write-Host "View output:  Receive-Job -Name forgeos-backend -Keep"
Write-Host "Stop everything:  Get-Job | Stop-Job; Get-Job | Remove-Job"
