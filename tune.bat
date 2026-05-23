@echo off
REM ----------------------------------------------------------------
REM RLQC -- double-click launcher for the calibration tuner.
REM Same shape as run.bat but launches tuner.py instead.
REM ----------------------------------------------------------------

setlocal
title RLQC - Tuner

where python >nul 2>nul
if errorlevel 1 (
    echo [ ERROR ] Python was not found on this PC.
    echo Please run  install.bat  first.
    echo.
    pause
    exit /b 1
)

python "%~dp0tuner.py"
if errorlevel 1 (
    echo.
    echo Tuner exited with an error. See the messages above.
    echo.
    pause
)
endlocal
