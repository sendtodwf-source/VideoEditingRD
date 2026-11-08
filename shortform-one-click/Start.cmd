@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Please copy the error above when asking for help.
  pause
)
