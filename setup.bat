@echo off
REM Shopify Verifier Setup Script for Windows

echo ==========================================
echo Shopify Store Verifier - Setup
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3 is not installed. Please install Python 3.10 or higher.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Create virtual environment (optional but recommended)
set /p create_venv="Create a virtual environment? (recommended) [Y/n]: "
if "%create_venv%"=="" set create_venv=Y

if /i "%create_venv%"=="Y" (
    echo Creating virtual environment...
    python -m venv venv
    
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo Virtual environment created and activated
    echo.
)

REM Install Python dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo Python dependencies installed
echo.

REM Install Playwright browsers
echo Installing Playwright browsers (this may take a few minutes)...
playwright install chromium

if errorlevel 1 (
    echo ERROR: Failed to install Playwright browsers
    pause
    exit /b 1
)

echo Playwright browsers installed
echo.

REM Create results directory
if not exist "results" mkdir results
echo Created results directory
echo.

echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Next steps:
echo.
echo 1. Quick test with sample stores:
echo    python quick_start.py
echo.
echo 2. Batch process your own stores:
echo    - Create a text file with store URLs (one per line)
echo    - Run: python batch_verifier.py
echo.
echo 3. Read the README for more details:
echo    type README.md
echo.

if /i "%create_venv%"=="Y" (
    echo Note: To activate the virtual environment in future sessions:
    echo       venv\Scripts\activate.bat
    echo.
)

echo ==========================================
pause
