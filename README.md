# CPL-2 Cold Rolling Line Scheduling System

A full-stack industrial scheduling system for JSW's
CPL-2 (Continuous Pickling Line 2) cold rolling line.

The system ingests HR stock reports (.xls / .xlsx), filters and
categorizes coils, optimizes production sequences according to
metallurgical constraints, detects rule violations, displays live KPI
metrics, supports manual planner reordering with instant violation
recomputation, and exports schedules to standardized Excel sheets.

---

## Key Features

- Automated Scheduling Engine
  - HRPO and HRSPO campaign: thick and thin sections are segregated,
    ordered by width taper, and constrained by jump limits and TDC
    separation.
  - NGO FP campaign: silicon-content bands, boundary rules, and width
    tapering within each band.
  - APL7 segregation: coils with Act Path = 7 or Prev Unit = 7 are
    quarantined into a dedicated export sheet.
- Interactive Planner Dashboard
  - Real-time KPI summary bar for tonnage, coil counts, age buckets,
    and violations.
  - Drag-and-drop reordering with immediate violation recomputation.
  - Finalization with state locking, override justification, and audit
    logging.
- Enterprise Authentication
  - Microsoft Entra ID support with MSAL.js and JWKS validation.
  - RBAC for planner and viewer roles.
- Portable and Self-Contained
  - Pure-Python Excel parsing and generation using xlrd and openpyxl.
  - SQLite for local development and PostgreSQL for deployment.

---

## How to Start the Project

### Prerequisites

Make sure the following are installed before continuing:

| Tool | Minimum Version | Download |
| :--- | :--- | :--- |
| Python | 3.10+ | <https://www.python.org/downloads/> |
| Node.js + npm | 18+ | <https://nodejs.org/> |
| Git | any | <https://git-scm.com/> |

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/komallalwani636-ship-it/JSW.git
cd JSW
```

---

### Step 2 — Configure Environment Variables

Copy the example environment file and (optionally) edit it:

```bash
# Linux / macOS / Git Bash
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env
```

The defaults work out-of-the-box for local development (SQLite database,
no Azure AD). Open `.env` to customise if needed:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./cpl2_dev.db` | Database connection string |
| `JWT_SECRET` | `cpl2_dev_secret_key_…` | JWT signing secret — **change in production** |
| `JWT_EXPIRY_MINUTES` | `60` | Token lifetime in minutes |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL used by the frontend |
| `AZURE_CLIENT_ID` | *(empty)* | Optional — Microsoft Entra ID SSO |
| `AZURE_TENANT_ID` | `common` | Optional — Microsoft Entra ID SSO |

---

### Step 3 — Install Dependencies & Initialise the Database

#### Option A — Automated one-command setup (recommended)

**Windows:**

```cmd
setup.bat
```

**Linux / macOS / Git Bash:**

```bash
chmod +x setup.sh start.sh run_tests.sh
./setup.sh
```

The script will:

1. Validate Python ≥ 3.10 and Node.js ≥ 18 are on `PATH`.
2. Create `.env` from `.env.example` if it does not already exist.
3. Create the `uploads/` directory for uploaded Excel files.
4. Install Python backend dependencies: `pip install -r backend/requirements.txt`
5. Install Node.js frontend dependencies: `npm install` (inside `frontend/`)
6. Apply database migrations: `alembic upgrade head`
7. Seed the default `planner` and `viewer` accounts.

#### Option B — Manual step-by-step setup

```bash
# 1. Install backend Python packages
pip install -r backend/requirements.txt

# 2. Install frontend Node packages
cd frontend
npm install
cd ..

# 3. Run database migrations
cd backend
python -m alembic upgrade head
cd ..

# 4. Seed default users (planner + viewer)
cd backend
python seed_users.py
cd ..

# 5. Create uploads directory
mkdir -p uploads          # Linux / macOS
# mkdir uploads           # Windows
```

---

### Step 4 — Start the Application

#### Option A — One-command launch (recommended)

**Windows:**

```cmd
start.bat
```

**Linux / macOS / Git Bash:**

```bash
./start.sh
```

This opens two terminal windows — one for the backend and one for the frontend.

#### Option B — Start each service manually

Open **two separate terminals** and run:

**Terminal 1 — Backend (FastAPI):**

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend (Vite/React):**

```bash
cd frontend
npm run dev
```

---

### Step 5 — Open the Application

| Service | URL |
| :--- | :--- |
| 🖥 Frontend (React app) | <http://localhost:5173> |
| ⚙️ Backend API | <http://localhost:8000> |
| 📄 Swagger / API docs | <http://localhost:8000/docs> |
| 🔍 ReDoc API docs | <http://localhost:8000/redoc> |

Log in with the default credentials:

| Role | Username | Password | Permissions |
| :--- | :--- | :--- | :--- |
| Planner | `planner` | `planner123` | Full write access (upload, schedule, finalize, export) |
| Viewer | `viewer` | `viewer123` | Read-only access |

---

### Step 6 — Run the Test Suite (Optional)

**Windows:**

```cmd
run_tests.bat
```

**Linux / macOS / Git Bash:**

```bash
./run_tests.sh
```

Or run pytest directly:

```bash
cd backend
python -m pytest tests/ -v
```

All 49 tests should pass. ✅

---

### Troubleshooting

| Problem | Solution |
| :--- | :--- |
| `python` not found | Use `python3` on Linux/macOS, or add Python to `PATH` |
| `npm` not found | Install Node.js 18+ from <https://nodejs.org/> |
| Port 8000 already in use | Change `--port` in `start.bat` / `start.sh` |
| Port 5173 already in use | Add `--port 5174` to the `npm run dev` command in `start.bat` / `start.sh` |
| Database errors on startup | Delete `backend/cpl2_dev.db` and re-run `alembic upgrade head` |
| `.env` missing | Run `copy .env.example .env` (Windows) or `cp .env.example .env` (Unix) |

---

## Microsoft Entra ID Configuration

To enable single sign-on:

1. Register an application in the Azure Portal under Entra ID.
2. Add a single-page app redirect URI for
   `http://localhost:5173`.
3. Add these values to your `.env` file:

   ```env
   AZURE_CLIENT_ID=<your-azure-app-client-id>
   AZURE_TENANT_ID=<your-azure-tenant-id-or-common>
   VITE_AZURE_CLIENT_ID=<your-azure-app-client-id>
   VITE_AZURE_TENANT_ID=<your-azure-tenant-id-or-common>
   ```

4. Restart the app. The login page will show the Microsoft sign-in
   option alongside the standard username/password flow.

---

## Project Structure

```text
JSW-main/
├── backend/
│   ├── alembic/                  # Database schema migrations
│   ├── api/
│   │   ├── routers/              # FastAPI endpoints
│   │   ├── dependencies.py       # Auth and DB injection
│   │   ├── ms_auth_service.py     # Entra ID token validation
│   │   └── schemas.py            # Pydantic v2 schemas
│   ├── db/
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   └── session.py            # DB engine and session setup
│   ├── engine/
│   │   ├── parser.py             # XLS/XLSX parser
│   │   ├── filter_pipeline.py    # Coil filtering and APL7 rules
│   │   ├── sequencer_hrpo.py     # HRPO/HRSPO sequencing logic
│   │   ├── sequencer_ngo.py      # NGO FP sequencing logic
│   │   ├── violation_detector.py # Rule violation checking
│   │   ├── kpi_calculator.py     # KPI calculation
│   │   └── exporter.py           # Excel export logic
│   ├── tests/                   # Property and integration tests
│   └── seed_users.py            # Default user seeding
├── frontend/
│   ├── src/
│   │   ├── api/                  # API client and hooks
│   │   ├── components/           # UI components
│   │   ├── pages/                # Dashboard and scheduling pages
│   │   ├── msalConfig.ts         # MSAL browser config
│   │   └── auth.tsx              # React auth context
├── docker/                      # Docker deployment files
├── docker-compose.yml           # Postgres + backend + frontend stack
├── setup.bat / setup.sh         # Clean-machine setup scripts
├── start.bat / start.sh         # App launch scripts
├── run_tests.bat / run_tests.sh # Full test runner scripts
└── README.md                    # Project documentation
```
