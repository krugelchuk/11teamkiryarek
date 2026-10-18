@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 scripts\prepare_demo.py
  if errorlevel 1 goto failed
  py -3 server.py --db data/demo.db
) else (
  python scripts\prepare_demo.py
  if errorlevel 1 goto failed
  python server.py --db data/demo.db
)
pause
exit /b
:failed
echo Demo preparation failed. Check Python 3.10+ and README.md.
pause
exit /b 1
