# Start Backend API
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\DELL\.gemini\antigravity\scratch\gomas_legal_engine; python api.py"

# Start Backend Worker (Watcher)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\DELL\.gemini\antigravity\scratch\gomas_legal_engine; python main.py"

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\DELL\.gemini\antigravity\scratch\gomas_legal_engine\frontend; npm run dev"

Write-Host "Systems launching..."
Write-Host "API: http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"
