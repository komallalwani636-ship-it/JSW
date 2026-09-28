#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  Starting CPL-2 Scheduling System"
echo "========================================================"
echo ""

if [ ! -f .env ]; then
    echo "[WARNING] .env not found. Running setup.sh first..."
    ./setup.sh
fi

echo "[INFO] Starting Backend on http://localhost:8000 ..."
(cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!

echo "[INFO] Starting Frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM EXIT

echo ""
echo "Application started!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."
wait
