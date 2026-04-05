@echo off
REM LinkedIn Carousel Screenshot Generator
REM This batch file installs dependencies and runs the screenshot script

echo.
echo =================================================
echo   LinkedIn Carousel Screenshot Generator
echo =================================================
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
echo Running screenshot generator...
echo.

python create_linkedin_slides.py

pause
