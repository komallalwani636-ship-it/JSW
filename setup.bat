@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   CPL-2 Scheduling System — Automated Setup (Windows)
echo ========================================================
echo.

:: 1. Validate Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and re-run this script.
    exit /b 1
)

python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10 or newer is required.
    exit /b 1
)
echo [OK] Python is installed.

:: 2. Validate Node.js & npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed or not in PATH.
    echo Please install Node.js 18+ from https://nodejs.org/ and re-run this script.
    exit /b 1
)
echo [OK] Node.js and npm are installed.

:: 3. Prepare Environment Configuration (.env)
if not exist .env (
    echo [INFO] Creating .env from .env.example...
    copy .env.example .env >nul
    echo [OK] .env created with sensible local defaults.
) else (
    echo [OK] .env already exists.
)

:: 4. Ensure uploads directory exists
if not exist uploads (
    mkdir uploads
    echo [OK] Created uploads/ directory.
)

:: 5. Install Backend Python Dependencies
echo.
echo [INFO] Installing backend Python dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    exit /b 1
)
echo [OK] Backend dependencies installed successfully.

:: 6. Install Frontend Node Dependencies
echo.
echo [INFO] Installing frontend npm dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install npm dependencies.
    cd ..
    exit /b 1
)
cd ..
echo [OK] Frontend dependencies installed successfully.

:: 7. Run Database Migrations
echo.
echo [INFO] Applying database migrations...
cd backend
python -m alembic upgrade head
if %errorlevel% neq 0 (
    echo [ERROR] Database migration failed.
    cd ..
    exit /b 1
)
echo [OK] Database schema up to date.

:: 8. Seed Default Users
echo.
echo [INFO] Seeding default planner and viewer accounts...
python seed_users.py
cd ..

echo.
echo ========================================================
echo   Setup Completed Successfully!
echo ========================================================
echo.
echo Default credentials:
echo   Planner:  username: planner   password: planner123
echo   Viewer:   username: viewer    password: viewer123
echo.
echo To start the application, run:
echo   start.bat
echo.
pause
