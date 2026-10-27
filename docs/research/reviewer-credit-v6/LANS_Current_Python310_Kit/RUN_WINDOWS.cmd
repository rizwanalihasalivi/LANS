@echo off
setlocal
cd /d "%~dp0"
py -3.10 -c "import sys; assert sys.version_info[:2]==(3,10)" >nul 2>nul
if errorlevel 1 goto use_python
py -3.10 -m venv .venv
goto install
:use_python
python -c "import sys; assert sys.version_info[:2]==(3,10)" >nul 2>nul
if errorlevel 1 goto python_missing
python -m venv .venv
:install
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe tools\controller_review\laptop_campaign6.py --profile fresh_history --output laptop-results
if errorlevel 1 goto failed
echo Completed. Send laptop-results\Results.zip for review.
pause
exit /b 0
:python_missing
echo Python 3.10 was not found. Install Python 3.10 and enable its PATH or py launcher.
:failed
echo Benchmark did not complete. Keep the error above and any partial results; do not overwrite them.
pause
exit /b 1
