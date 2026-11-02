@echo off
echo ========================================
echo   Multi-Agent Enterprise BI Dashboard
echo ========================================

cd C:\Users\siris\sirish_ai

:: Stop any old copies first so ports and the ngrok URL are free
taskkill /F /IM ngrok.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8502 " ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1

echo [1/2] Starting Streamlit on port 8502...
:: Running Streamlit in its own window
start "Streamlit" cmd /k "streamlit run app.py --server.port 8502"

echo Waiting for Streamlit to boot...
timeout /t 5 /nobreak > nul

:: The Microsoft Store version of ngrok reads a hidden copy of ngrok.yml.
:: Copy the real one over it so edits in AppData\Local\ngrok always take effect.
copy /Y "%LOCALAPPDATA%\ngrok\ngrok.yml" "%LOCALAPPDATA%\Packages\ngrok.ngrok_1g87z0zv29zzc\LocalCache\Local\ngrok\ngrok.yml" >nul 2>&1

echo [2/2] Starting ngrok (Google login)...
:: Starts only the bi-app endpoint (with Google login) from ngrok.yml
start "ngrok" cmd /k "ngrok start bi-app"

echo.
echo Dashboard is live!
echo URL: https://sirish.ngrok.app  (Google sign-in required)
echo.
pause
