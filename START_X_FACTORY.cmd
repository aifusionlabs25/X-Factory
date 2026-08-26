@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
python -B scripts\mission_control_server.py --open
if errorlevel 1 pause
