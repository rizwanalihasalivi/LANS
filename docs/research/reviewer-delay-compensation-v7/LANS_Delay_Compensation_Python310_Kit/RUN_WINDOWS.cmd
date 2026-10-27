@echo off
cd /d "%~dp0"
py -3.10 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\controller_review\laptop_full_controller.py --profile delay_compensated --output laptop-results
pause
