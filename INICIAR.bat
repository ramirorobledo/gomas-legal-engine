@echo off
cd /d "%~dp0"
title Gomas Legal Engine

set PYTHON=C:\Users\RAMIRO\AppData\Local\Programs\Python\Python310\python.exe
set NPM=C:\Program Files\nodejs\npm.cmd
set DIR=%~dp0

echo ============================================
echo   GOMAS LEGAL ENGINE
echo ============================================
echo.

REM --- Matar procesos previos ---
echo Cerrando servicios anteriores...
taskkill /F /FI "WINDOWTITLE eq API REST - Gomas*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq WATCHDOG - Gomas*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FRONTEND - Gomas*" >nul 2>&1
timeout /t 2 /nobreak >nul

REM --- Verificar .env ---
if not exist "%DIR%.env" (
    echo [ERROR] No se encontro el archivo .env
    pause
    exit /b 1
)

REM --- Terminal 1: API REST ---
echo [1/3] Iniciando API REST en puerto 8000...
start "API REST - Gomas Legal" cmd /k "cd /d %DIR% && %PYTHON% -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 4 /nobreak >nul

REM --- Terminal 2: Watchdog ---
echo [2/3] Iniciando Watchdog...
start "WATCHDOG - Gomas Legal" cmd /k "cd /d %DIR% && %PYTHON% main.py"
timeout /t 3 /nobreak >nul

REM --- Terminal 3: Frontend ---
echo [3/3] Iniciando Frontend en puerto 3000...
if not exist "%DIR%frontend\node_modules" (
    echo    [instalando dependencias primero...]
    start "FRONTEND - Gomas Legal" cmd /k "cd /d %DIR%frontend && %NPM% install && %NPM% run dev"
) else (
    start "FRONTEND - Gomas Legal" cmd /k "cd /d %DIR%frontend && %NPM% run dev"
)

echo.
echo ============================================
echo   Sistema iniciado.
echo   Abriendo navegador en 8 segundos...
echo ============================================
timeout /t 8 /nobreak >nul
start http://localhost:3000

echo.
echo Todo listo. Puedes cerrar esta ventana.
echo Para detener: cierra las 3 ventanas negras (API REST, WATCHDOG, FRONTEND).
pause
