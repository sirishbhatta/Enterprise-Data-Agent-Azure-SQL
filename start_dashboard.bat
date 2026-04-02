@echo off
echo ========================================
echo   Multi-Agent Enterprise BI Dashboard
echo ========================================

cd C:\Users\siris\sirish_ai

echo [1/2] Starting Streamlit on port 8502...
:: Running Streamlit in its own window
start "Streamlit" cmd /k "streamlit run app.py --server.port 8502"

echo Waiting for Streamlit to boot...
timeout /t 5 /nobreak > nul

echo [2/2] Starting Dual ngrok Tunnels...
:: This starts BOTH the new domain and your resume link
start "ngrok" cmd /k "ngrok start --all"

echo.
echo Dashboard is live!
echo Primary: https://sirish.ngrok.app
echo Resume:  https://abbey-unsoporiferous-ara.ngrok-free.dev
echo.
pause