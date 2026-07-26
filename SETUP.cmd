@echo off
REM ============================================================
REM  Private Brain — ONE-CLICK SIDELOAD into existing Codex CLI
REM  Double-click this file. Codex must already be installed.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  ========================================================
echo   PRIVATE BRAIN  -  CODEX SIDELOAD INSTALLER
echo   (does NOT replace codex — wires into it)
echo  ========================================================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
  echo ERROR: PowerShell not found.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP.ps1"
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo INSTALL FAILED code %ERR%
  pause
  exit /b %ERR%
)
echo.
echo  Press any key to close...
pause >nul
exit /b 0
