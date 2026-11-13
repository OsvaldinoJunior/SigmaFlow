@echo off
cd /d "%~dp0"
echo Iniciando SigmaFlow em http://127.0.0.1:8765
echo Mantenha esta janela aberta enquanto usar a interface.
python -c "import numpy, pandas, scipy, openpyxl, xlrd" >nul 2>&1
if errorlevel 1 (
  echo Dependencias locais ausentes no Python ativo.
  echo Instale com: python -m pip install -r requirements-local.txt
  pause
  exit /b 1
)
python sigmaflow\local_app.py
echo.
echo A interface foi encerrada. Confira acima se ocorreu algum erro.
pause
