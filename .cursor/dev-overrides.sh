# Safe, isolated LOCAL development overrides for the PronoStats API.
#
# Cloud Agent secrets are injected as OS environment variables, and
# pydantic-settings gives OS env vars precedence over the .env file. In this
# repo several injected secrets (DATABASE_URL, ENVIRONMENT, JWT_COOKIE_*) point
# the app at the remote Supabase database. Because the app's own seed/bootstrap
# performs a destructive drop_all()+create_all(), running it against that remote
# database would wipe it.
#
# Sourcing this file forces every local process (install-time seed and the API
# server) onto an isolated SQLite database in development mode, so the dev
# environment can never read from or write to the remote database. JWT_SECRET is
# intentionally left untouched: the injected value (or the one generated in
# .env) is reused so sessions stay valid.
export ENVIRONMENT=development
export DATABASE_URL=BDD_CLOUD
export JWT_COOKIE_SECURE=false
export JWT_COOKIE_SAMESITE=lax
export CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
export FRONTEND_URL="http://localhost:5173"
