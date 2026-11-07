@echo off
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0Build-And-Install.ps1"
set "PBZ_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %PBZ_RESULT%
