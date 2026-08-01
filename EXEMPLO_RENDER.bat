@echo off
cd /d "%~dp0"
echo Edite os caminhos de AUDIO e PERSONAGEM antes de executar.
set AUDIO=C:\caminho\musica.wav
set PERSONAGEM=C:\caminho\personagem.png
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% cyberpunk.py render "%AUDIO%" output\exemplo.mp4 --character "%PERSONAGEM%::protagonist::auto::Protagonista" --world auto_director --continuity-strength 0.84 --secondary-motion 0.70 --width 1280 --height 720 --render-scale 0.5 --preview-seconds 15
pause
