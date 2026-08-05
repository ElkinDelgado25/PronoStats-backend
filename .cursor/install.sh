#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the PronoStats FastAPI backend.
# Safe to run repeatedly: it refreshes the virtualenv/dependencies, ensures a
# local dev .env exists, and seeds an ISOLATED local SQLite database.
#
# IMPORTANT: Cloud Agent secrets (DATABASE_URL, ENVIRONMENT, ...) are injected as
# OS env vars and take precedence over .env in pydantic-settings. To keep the dev
# environment from ever touching the injected remote database, all DB work below
# runs with the local-dev overrides in .cursor/dev-overrides.sh and is guarded so
# the destructive seed only ever runs against local SQLite.
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
#    Provides a fallback JWT_SECRET when none is injected; DB/env are forced to
#    local dev values at runtime via .cursor/dev-overrides.sh.
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

# 4) Seed an ISOLATED local SQLite database with demo users and sample data.
#    Force local-dev config, then hard-guard: refuse to seed anything that is not
#    local SQLite so an injected remote DATABASE_URL can never be wiped.
# shellcheck disable=SC1091
source .cursor/dev-overrides.sh

EFFECTIVE_DB="$(./.venv/bin/python - <<'PY'
from app.core.config import settings
print(settings.effective_database_url)
PY
)"

case "$EFFECTIVE_DB" in
  sqlite:*)
    echo "[install] Seeding local SQLite database (${EFFECTIVE_DB})."
    ./.venv/bin/python -m app.seed
    ;;
  *)
    echo "[install] SAFETY ABORT: effective database is not local SQLite." >&2
    echo "[install] Refusing to run the destructive seed against: ${EFFECTIVE_DB%%@*}@<redacted>" >&2
    exit 1
    ;;
esac

echo "[install] PronoStats backend environment is ready."
