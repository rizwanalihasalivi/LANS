@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto missing_python
set "python_version="
for %%V in (3.11 3.12 3.13 3.14) do (
  if not defined python_version (
    py -%%V -c "import sys,struct; assert sys.version_info >= (3,11) and struct.calcsize('P') == 8" >nul 2>nul
    if not errorlevel 1 set "python_version=%%V"
  )
)
if not defined python_version goto missing_python
if not exist ".venv-modern\Scripts\python.exe" (
  py -%python_version% -m venv .venv-modern
  if errorlevel 1 goto failed
)
".venv-modern\Scripts\python.exe" -c "import sys,struct; assert sys.version_info >= (3,11) and struct.calcsize('P') == 8"
if errorlevel 1 (
  echo This environment is unsuitable. Extract the new kit into a fresh folder and run again.
  goto failed
)
".venv-modern\Scripts\python.exe" --version
".venv-modern\Scripts\python.exe" -m pip install --disable-pip-version-check --only-binary=:all: "numpy>=1.23,<3"
if errorlevel 1 goto failed
set "result_folder=laptop-results-modern-%RANDOM%-%RANDOM%"
".venv-modern\Scripts\python.exe" laptop_benchmark.py --output "%result_folder%"
if errorlevel 1 goto failed
echo.
echo Finished. Send summary.json and CSVs from %result_folder% back to this chat.
echo Keep the earlier Python 3.10 results for comparison.
echo This measures laptop CPU and IPC. It is not vehicle or actuator validation.
pause
exit /b 0
:missing_python
echo Install 64-bit Python 3.11 or newer from python.org, then run this file again.
echo Python 3.10 is not selected because its Windows sleep implementation differs.
pause
exit /b 1
:failed
echo Benchmark did not complete. Please share the displayed error. Do not label it a passed test.
pause
exit /b 1
