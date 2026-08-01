@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3.12) else (set PY=python)
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Instalacao concluida. Confirme que FFmpeg esta no PATH.
pause
