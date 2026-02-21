@echo off
echo Cerrando Claude Desktop...
taskkill /F /IM "Claude.exe" >nul 2>&1
taskkill /F /IM "claude.exe" >nul 2>&1
timeout /t 2 /nobreak >nul

echo Escribiendo configuracion MCP...
(
echo {
echo   "preferences": {
echo     "coworkScheduledTasksEnabled": false,
echo     "sidebarMode": "code"
echo   },
echo   "mcpServers": {
echo     "gomas-legal-engine": {
echo       "command": "C:\Users\RAMIRO\AppData\Local\Programs\Python\Python310\python.exe",
echo       "args": ["C:\Users\RAMIRO\Documents\GitHub\gomas-legal-engine\mcp_server.py"],
echo       "cwd": "C:\Users\RAMIRO\Documents\GitHub\gomas-legal-engine"
echo     }
echo   }
echo }
) > "C:\Users\RAMIRO\AppData\Roaming\Claude\claude_desktop_config.json"

echo Reiniciando Claude Desktop...
start "" "C:\Users\RAMIRO\AppData\Local\AnthropicClaude\Claude.exe"

echo Listo. Claude Desktop se esta reiniciando con el MCP configurado.
timeout /t 3
