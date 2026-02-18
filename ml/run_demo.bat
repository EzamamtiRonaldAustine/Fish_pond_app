@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo  Fish Pond ML Model Demo
echo ========================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    pause
    exit /b 1
)

REM Check if venv exists, create if not
if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

REM Install requirements
if exist requirements.txt (
    echo [INFO] Installing/Updating dependencies...
    pip install -r requirements.txt >nul
) else (
    echo [WARNING] requirements.txt not found.
)

REM Run the demo script
echo.
echo [INFO] Running demo.py...
echo ----------------------------------------
python demo.py
echo ----------------------------------------
echo.

pause
