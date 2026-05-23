@echo off
REM ----------------------------------------------------------------
REM RLQC -- double-click launcher.
REM Runs the main script using the system Python. If the script
REM exits with an error we keep the window open so the user can
REM read what went wrong; on a clean exit the window closes by
REM itself.
REM ----------------------------------------------------------------

setlocal
title RLQC

where python >nul 2>nul
if errorlevel 1 (
    echo [ ERROR ] Python was not found on this PC.
    echo Please run  install.bat  first.
    echo.
    pause
    exit /b 1
)

python "%~dp0RLQuickChat.py"
if errorlevel 1 (
    echo.
    echo RLQC exited with an error. See the messages above.
    echo.
    pause
)
endlocal
