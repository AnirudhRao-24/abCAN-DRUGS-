@echo off
echo =========================================
echo Starting abCAN-DRUGS Servers...
echo =========================================

echo.
echo [1/3] Starting FastAPI Backend (Port 8000)...
start "abCAN-DRUGS Backend" cmd /k "python server.py"

echo.
echo [2/3] Starting Vite Frontend (Port 5173)...
cd frontend
start "abCAN-DRUGS Frontend" cmd /k "npm run dev"

echo.
echo [3/3] Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

echo.
echo Launching dashboard in your default browser!
start http://localhost:5173

echo.
echo Setup complete. You can safely close this launch window.
echo (To stop the servers later, simply close their respective terminal windows.)
pause
