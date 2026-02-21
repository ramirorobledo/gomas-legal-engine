@echo off
echo ============================================
echo   Reiniciando Claude Desktop + MCP Server
echo ============================================
echo.

echo [1/3] Cerrando Claude Desktop...
taskkill /F /IM claude.exe >nul 2>&1
if %errorlevel%==0 (
    echo       Claude Desktop cerrado.
) else (
    echo       Claude Desktop no estaba corriendo.
)

echo [2/3] Esperando 3 segundos...
timeout /t 3 /nobreak >nul

echo [3/3] Abriendo Claude Desktop...
start "" explorer.exe "shell:AppsFolder\Claude_pzs8sxrjxfjjc!App"

echo.
echo ============================================
echo   Listo! Claude Desktop se esta abriendo.
echo   Espera ~10 segundos y verifica que el MCP
echo   aparezca como "connected" en Configuracion
echo   ^> Servidores MCP locales.
echo ============================================
echo.
pause
