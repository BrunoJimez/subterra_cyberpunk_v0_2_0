@echo off
cd /d "%~dp0"
echo Edite os caminhos antes de executar.
set AUDIO=C:\caminho\musica.wav
set PERSONAGEM=C:\caminho\personagem.png
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% cyberpunk.py render "%AUDIO%" output\i2v_preview.mp4 --character "%PERSONAGEM%::protagonist::auto::Protagonista" --i2v-mode package --i2v-package-dir output\i2v_packages --width 1280 --height 720 --render-scale 0.5 --preview-seconds 15
pause
