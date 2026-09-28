#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  CPL-2 Scheduling System — Automated Setup (Unix/macOS)"
echo "========================================================"
echo ""

# 1. Validate Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    exit 1
fi

python3 -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'" || {
    echo "[ERROR] Python 3.10 or newer is required."
    exit 1
}
echo "[OK] Python is installed."

# 2. Validate Node.js & npm
if ! command -v npm >/dev/null 2>&1; then
    echo "[ERROR] Node.js / npm is not installed or not in PATH."
    exit 1
fi
echo "[OK] Node.js and npm are installed."

# 3. Prepare Environment Configuration (.env)
if [ ! -f .env ]; then
    echo "[INFO] Creating .env from .env.example..."
    cp .env.example .env
    echo "[OK] .env created."
else
    echo "[OK] .env already exists."
fi

# 4. Ensure uploads directory exists
mkdir -p uploads
echo "[OK] uploads/ directory ready."

# 5. Install Backend Python Dependencies
echo ""
echo "[INFO] Installing backend Python dependencies..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install -r backend/requirements.txt
echo "[OK] Backend dependencies installed."

# 6. Install Frontend Node Dependencies
echo ""
echo "[INFO] Installing frontend npm dependencies..."
(cd frontend && npm install)
echo "[OK] Frontend dependencies installed."

# 7. Run Database Migrations
echo ""
echo "[INFO] Applying database migrations..."
(cd backend && python3 -m alembic upgrade head)
echo "[OK] Database schema up to date."

# 8. Seed Default Users
echo ""
echo "[INFO] Seeding default planner and viewer accounts..."
(cd backend && python3 seed_users.py)

echo ""
echo "========================================================"
echo "  Setup Completed Successfully!"
echo "========================================================"
echo ""
echo "Default credentials:"
echo "  Planner:  username: planner   password: planner123"
echo "  Viewer:   username: viewer    password: viewer123"
echo ""
echo "To start the application, run:"
echo "  ./start.sh"
echo ""
