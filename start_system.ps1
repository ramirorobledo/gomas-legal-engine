# Start Backend API
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python api.py"

# Start Backend Worker (Watcher)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python main.py"

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Systems launching..."
Write-Host "API: http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"
