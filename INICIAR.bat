@echo off
cd /d "%~dp0"
title Gomas Legal Engine

echo ============================================
echo   GOMAS LEGAL ENGINE
echo ============================================
echo.

REM --- Matar procesos previos para evitar duplicados ---
echo Cerrando servicios anteriores...
taskkill /F /FI "WINDOWTITLE eq API REST - Gomas*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq WATCHDOG - Gomas*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FRONTEND - Gomas*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FRONTEND INSTALL*" >nul 2>&1
timeout /t 2 /nobreak >nul

REM --- Verificar .env ---
if not exist ".env" (
    echo [ERROR] No se encontro el archivo .env
    pause
    exit /b 1
)

REM --- Terminal 1: API REST ---
echo [1/3] Iniciando API REST...
start "API REST - Gomas Legal" cmd /k "cd /d %~dp0 && uvicorn api:app --reload --port 8000"
timeout /t 3 /nobreak >nul

REM --- Terminal 2: Watchdog ---
echo [2/3] Iniciando Watchdog...
start "WATCHDOG - Gomas Legal" cmd /k "cd /d %~dp0 && python main.py"
timeout /t 3 /nobreak >nul

REM --- Terminal 3: Frontend ---
echo [3/3] Iniciando Frontend...
if not exist "frontend\node_modules" (
    start "FRONTEND - Gomas Legal" cmd /k "cd /d %~dp0\frontend && npm install && npm run dev"
) else (
    start "FRONTEND - Gomas Legal" cmd /k "cd /d %~dp0\frontend && npm run dev"
)

echo.
echo ============================================
echo   Sistema iniciado.
echo   Abriendo navegador en 8 segundos...
echo ============================================
timeout /t 8 /nobreak >nul
start http://localhost:3000

echo.
echo Cierra esta ventana cuando quieras.
echo Para detener todo, cierra las 3 ventanas negras.
pause
