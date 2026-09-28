@echo off
setlocal

echo ========================================================
echo   Running CPL-2 Backend and Frontend Test Suites
echo ========================================================
echo.

echo [1/2] Running Backend Tests (pytest)...
cd backend
python -m pytest -v
if %errorlevel% neq 0 (
    echo [ERROR] Backend tests failed.
    cd ..
    exit /b 1
)
cd ..
echo [OK] Backend tests passed.
echo.

echo [2/2] Running Frontend Tests (vitest)...
cd frontend
call npm run test
if %errorlevel% neq 0 (
    echo [ERROR] Frontend tests failed.
    cd ..
    exit /b 1
)
cd ..
echo [OK] Frontend tests passed.
echo.

echo ========================================================
echo   All Tests Passed Successfully!
echo ========================================================
