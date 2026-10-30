@echo off
rem One-click launcher: Edit Flow
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launch.py editor
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python launch.py editor
  goto :eof
)
echo.
echo Python 3 was not found. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this again.
echo.
pause
