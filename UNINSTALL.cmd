@echo off
REM Windows one-click uninstaller (double-click)
cd /d "%~dp0"
echo.
echo  Private Brain — UNINSTALL from Codex
echo  Codex CLI stays. Graph archived by default.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0UNINSTALL.ps1" %*
echo.
pause
exit /b %ERRORLEVEL%
