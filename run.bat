@echo off
echo Starting Python Serial Terminal + STM32 Flasher...
python cli.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
