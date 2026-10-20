@echo off
title FinBridge server (do not close this window)
cd /d "%~dp0backend"

set PY=
python --version >nul 2>&1 && set PY=python
if not defined PY ( py --version >nul 2>&1 && set PY=py )
if not defined PY (
  echo.
  echo [ERROR] Python is not installed or not in PATH.
  echo Install Python from https://www.python.org/downloads/  and tick "Add python.exe to PATH".
  echo Then close this window and double-click run.bat again.
  pause
  exit /b 1
)

echo Using: %PY%
echo Installing libraries (first time may take a minute)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Library install failed. Check your internet connection, then run again.
  pause
  exit /b 1
)

echo.
echo Starting FinBridge. The browser opens in a few seconds: http://localhost:8000
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8000"
%PY% -m uvicorn app.main:app --port 8000
echo.
echo [The server stopped. Read the message above for the reason.]
pause
