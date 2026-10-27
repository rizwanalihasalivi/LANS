@echo off
setlocal
cd /d "%~dp0"
set "python310="
py -3.10 -c "import sys,struct; assert sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8" >nul 2>nul
if not errorlevel 1 set "python310=py -3.10"
if not defined python310 (
  python -c "import sys,struct; assert sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8" >nul 2>nul
  if not errorlevel 1 set "python310=python"
)
if not defined python310 (
  echo Python 3.10 64-bit was not found. Share this error; no upgrade is required by this kit.
  goto failed
)
if not exist ".venv310\Scripts\python.exe" (
  %python310% -m venv .venv310
  if errorlevel 1 goto failed
)
".venv310\Scripts\python.exe" -c "import sys,struct; assert sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8"
if errorlevel 1 goto failed
".venv310\Scripts\python.exe" -m pip install --disable-pip-version-check --only-binary=:all: numpy==2.2.6
if errorlevel 1 goto failed
set "result_folder=laptop-results-py310-timer-%RANDOM%-%RANDOM%"
".venv310\Scripts\python.exe" laptop_benchmark.py --output "%result_folder%" --timer auto
if errorlevel 1 goto failed
echo Finished. Send summary.json and CSVs from %result_folder%.
echo Keep the previous run. This is CPU/IPC timing, not vehicle validation.
pause
exit /b 0
:failed
echo Benchmark did not complete. Please share the error above.
pause
exit /b 1
