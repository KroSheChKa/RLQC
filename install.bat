@echo off
REM ----------------------------------------------------------------
REM RLQC -- one-click dependency installer.
REM
REM Double-click this file. It will:
REM   1. Verify that Python is installed and on PATH.
REM   2. Run "pip install -r requirements.txt" on the user's behalf
REM      so no terminal commands are needed.
REM   3. Tell the user it's done, and wait for any key before closing
REM      so the window doesn't disappear before they can read it.
REM ----------------------------------------------------------------

setlocal
title RLQC - Installer

echo.
echo ============================================================
echo   RLQC -- installing dependencies
echo ============================================================
echo.

REM ---- Find Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ ERROR ] Python was not found on this PC.
    echo.
    echo Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: in the very first Python installer screen,
    echo tick the checkbox "Add python.exe to PATH" before
    echo clicking Install. Then run this installer again.
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM ---- Make sure pip itself is current; ignore failure here ----
python -m pip install --upgrade pip --disable-pip-version-check >nul 2>nul

REM ---- Install RLQC's runtime deps (pynput, pywin32, PyQt5) ----
echo Installing required packages: pynput, pywin32, PyQt5 ...
echo (first run can take a minute or two -- please wait)
echo.

python -m pip install --user --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [ ERROR ] Package installation failed.
    echo.
    echo Things to try:
    echo   * check your internet connection
    echo   * re-run this installer
    echo   * if Python was installed for "all users", right-click
    echo     install.bat and choose "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Done! All packages are installed.
echo.
echo   You can now launch RLQC by double-clicking  run.bat
echo   This window can be closed.
echo ============================================================
echo.
pause
endlocal
