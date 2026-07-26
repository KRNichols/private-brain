@echo off
REM Private Brain — Windows Day-1 (double-click)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START.ps1" %*
exit /b %ERRORLEVEL%
