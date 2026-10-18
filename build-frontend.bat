@echo off
cd /d "%~dp0frontend"
call npm ci --no-audit --no-fund
if errorlevel 1 goto failure
call npm run build
if errorlevel 1 goto failure
echo Frontend built. Run start.bat from the project root.
pause
exit /b 0
:failure
echo Build failed. See the error above.
pause
exit /b 1
