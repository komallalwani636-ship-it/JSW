@echo off
setlocal

echo ========================================================
echo   Starting CPL-2 Scheduling System
echo ========================================================
echo.

if not exist .env (
    echo [WARNING] .env not found. Running setup.bat first...
    call setup.bat
)

echo [INFO] Starting Backend on http://localhost:8000 ...
start "CPL-2 Backend (FastAPI)" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [INFO] Starting Frontend on http://localhost:5173 ...
start "CPL-2 Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo Application started!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
