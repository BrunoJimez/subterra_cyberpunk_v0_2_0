@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% cyberpunk.py diagnose --output hardware_report.json
pause
