#!/usr/bin/env bash
# Open an interactive psql session against local Docker Postgres or Supabase,
# reading credentials from the matching .env file.
#
# Usage:
#   ./connect_db.sh            -> connects using .env (local Docker Postgres)
#   ./connect_db.sh supabase   -> connects using .env.supabase

set -euo pipefail

ENV_FILE=".env"
if [ "${1:-}" = "supabase" ]; then
  ENV_FILE=".env.supabase"
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found in the current directory." >&2
  exit 1
fi

# Clear any leftover POSTGRES_* variables from a previous `source .env...`
# in this same shell session, so nothing "sticks" between connections.
unset POSTGRES_HOST POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT POSTGRES_SSLMODE

# Load variables from the .env file into this shell
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

HOST="${POSTGRES_HOST:-localhost}"
SSLMODE_PARAM=""
if [ -n "${POSTGRES_SSLMODE:-}" ]; then
  SSLMODE_PARAM="?sslmode=${POSTGRES_SSLMODE}"
fi

echo "Connecting to ${HOST}:${POSTGRES_PORT}/${POSTGRES_DB} (using ${ENV_FILE})..."

psql "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${HOST}:${POSTGRES_PORT}/${POSTGRES_DB}${SSLMODE_PARAM}"