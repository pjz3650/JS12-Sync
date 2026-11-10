@echo off
setlocal
cd /d "%~dp0"
py -3.13 -c "import tkinter" >nul 2>&1
if errorlevel 1 (
  echo Instale Python 3.13 para Windows com Python Launcher e Tcl/Tk.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -3.13 -m venv "mp4-sync\.venv"
if errorlevel 1 goto :failed
"mp4-sync\.venv\Scripts\python.exe" -m pip install -r "mp4-sync\requirements-lock.txt"
if errorlevel 1 goto :failed
"mp4-sync\.venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto :failed
"mp4-sync\.venv\Scripts\python.exe" -m spotdl --download-ffmpeg
if errorlevel 1 goto :failed
"mp4-sync\.venv\Scripts\python.exe" -m spotdl --download-deno
if errorlevel 1 goto :failed
echo Instalacao concluida. Abra mp4-sync\Abrir JS12 Sync.cmd.
pause
exit /b 0
:failed
echo A instalacao falhou. Confira a mensagem acima e a conexao com a internet.
pause
exit /b 1
