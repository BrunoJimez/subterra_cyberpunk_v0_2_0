@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% cyberpunk.py i2v-status output\i2v_packages output\i2v_clips
pause
