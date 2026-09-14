@echo off
REM ---------------------------------------------------------------------------
REM Build MeasureLog.exe on this Windows machine.
REM
REM Needs Python 3.9 or newer from python.org, with "Add Python to PATH" ticked.
REM Run it by double-clicking, or from a command prompt in the project folder.
REM The finished program lands in  dist\MeasureLog.exe
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0\.."

echo.
echo === MeasureLog build ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on this computer.
    echo Install it from https://www.python.org/downloads/windows/
    echo and tick "Add python.exe to PATH" during setup.
    goto :fail
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo Python 3.9 or newer is required.
    python --version
    goto :fail
)

echo [1/4] Installing build tools...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements-build.txt --quiet
if errorlevel 1 goto :fail

echo [2/4] Running the tests...
python -m unittest discover -s tests
if errorlevel 1 (
    echo.
    echo Tests failed - stopping so a broken build is not shipped.
    goto :fail
)

echo [3/4] Building the executable...
python -m PyInstaller packaging\MeasureLog.spec --noconfirm --clean
if errorlevel 1 goto :fail

echo [4/4] Checking the executable...
if not exist "dist\MeasureLog.exe" (
    echo dist\MeasureLog.exe was not produced.
    goto :fail
)
dist\MeasureLog.exe --selftest
if errorlevel 1 (
    echo The built program failed its self-test.
    goto :fail
)

echo.
echo === Done ===
echo Your program is here:  %CD%\dist\MeasureLog.exe
echo Copy that one file anywhere you like - it needs nothing else.
echo.
pause
exit /b 0

:fail
echo.
echo Build failed. Nothing was changed outside this folder.
echo.
pause
exit /b 1
