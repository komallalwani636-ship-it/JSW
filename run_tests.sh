#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  Running CPL-2 Backend and Frontend Test Suites"
echo "========================================================"
echo ""

echo "[1/2] Running Backend Tests (pytest)..."
(cd backend && python3 -m pytest -v)
echo "[OK] Backend tests passed."
echo ""

echo "[2/2] Running Frontend Tests (vitest)..."
(cd frontend && npm run test)
echo "[OK] Frontend tests passed."
echo ""

echo "========================================================"
echo "  All Tests Passed Successfully!"
echo "========================================================"
