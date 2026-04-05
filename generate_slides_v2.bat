@echo off
REM LinkedIn Carousel Screenshot Generator v2
REM This batch file installs dependencies and runs the improved screenshot script

echo.
echo ===========================================================
echo   LinkedIn Carousel Screenshot Generator v2
echo   (Improved Navigation & Mobile Optimization)
echo ===========================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org
    pause
    exit /b 1
)

echo Installing Playwright...
pip install playwright --quiet

if %errorlevel% neq 0 (
    echo Error: Failed to install Playwright
    pause
    exit /b 1
)

echo Installing Chromium browser...
playwright install chromium

if %errorlevel% neq 0 (
    echo Error: Failed to install Chromium
    pause
    exit /b 1
)

echo.
echo Running improved screenshot generator...
echo.

python create_linkedin_slides_v2.py

pause
