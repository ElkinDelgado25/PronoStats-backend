#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the PronoStats FastAPI backend.
# Safe to run repeatedly: it refreshes the virtualenv/dependencies, ensures a
# local dev .env exists, and seeds the SQLite database with demo data.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"

# 0) Ensure the stdlib venv module is available. The default Cloud Agent image
#    ships Python 3.12 but not python3-venv, so install it once if missing.
if ! "$PYTHON_BIN" -c "import ensurepip" >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y python3-venv
  else
    apt-get update -qq
    apt-get install -y python3-venv
  fi
fi

# 1) Virtualenv (isolated from the system interpreter; avoids PEP 668 issues).
if [ ! -x ".venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# 2) Python dependencies (pinned in requirements.txt).
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

# 3) Local development .env (only created if missing so it is never overwritten).
#    Defaults keep the app on local SQLite; JWT_SECRET is generated once.
if [ ! -f ".env" ]; then
  DEV_JWT_SECRET="$(./.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
  cat > .env <<EOF
ENVIRONMENT=development
DATABASE_URL=BDD_CLOUD
JWT_SECRET=${DEV_JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_COOKIE_SECURE=false
JWT_COOKIE_SAMESITE=lax
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_URL=http://localhost:5173
EOF
  echo "[install] Created development .env with a generated JWT_SECRET."
else
  echo "[install] Existing .env kept as-is."
fi

# 4) Seed the local database with demo users and sample data.
./.venv/bin/python -m app.seed

echo "[install] PronoStats backend environment is ready."
