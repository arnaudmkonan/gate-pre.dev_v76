#!/bin/bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head

exec "$@"
