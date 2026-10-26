@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python is missing. Install 64-bit Python 3.11 or newer from python.org, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check "numpy>=1.23,<3"
if errorlevel 1 goto failed
set "result_folder=laptop-results-%RANDOM%-%RANDOM%"
".venv\Scripts\python.exe" laptop_benchmark.py --output "%result_folder%"
if errorlevel 1 goto failed
echo.
echo Finished. Send the summary.json from %result_folder% back to this chat.
echo This measures laptop CPU and IPC. It is not vehicle or actuator validation.
pause
exit /b 0
:failed
echo Benchmark did not complete. Please share the displayed error. Do not label it a passed test.
pause
exit /b 1
