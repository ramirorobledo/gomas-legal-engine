@echo off
cd /d "%~dp0"
echo ============================================
echo   GOMAS LEGAL ENGINE - Instalador
echo ============================================
echo.
echo [1/3] Instalando dependencias Python...
pip install watchdog anthropic pymupdf ftfy loguru aiofiles tiktoken python-multipart mcp
echo.
echo [2/3] Instalando modelo de spacy en español...
python -m spacy download es_core_news_sm
echo.
echo [3/3] Instalando dependencias del frontend...
cd frontend
npm install
cd ..
echo.
echo ============================================
echo   LISTO. Ahora haz doble-click en INICIAR.bat
echo ============================================
pause
