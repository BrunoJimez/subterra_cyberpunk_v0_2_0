@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% tests\character_test.py
if errorlevel 1 goto erro
%PY% tests\style_test.py
if errorlevel 1 goto erro
%PY% tests\continuity_i2v_test.py
if errorlevel 1 goto erro
%PY% tests\smoke_test.py
if errorlevel 1 goto erro
echo Todos os testes passaram.
pause
exit /b 0
:erro
echo Um teste falhou.
pause
exit /b 1
