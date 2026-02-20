# Start Gomas Legal Engine (Watchdog + API + Frontend)

Write-Host "Starting API SERVER..."
Start-Process "cmd" -ArgumentList "/k uvicorn api:app --reload --port 8000"

Write-Host "Starting WATCHDOG..."
Start-Process "cmd" -ArgumentList "/k python main.py"

Write-Host "Checking FRONTEND dependencies..."
Set-Location frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies (this may take a while)..."
    Start-Process "cmd" -ArgumentList "/c npm.cmd install" -Wait
}

Write-Host "Starting FRONTEND..."
Start-Process "cmd" -ArgumentList "/k npm.cmd run dev"


