#!/bin/bash
# Add (or with --wipe, remove) fake demo data on the running site.
# Run on the server from the repo root: sudo scripts/seed-demo.sh [--wipe]
set -euo pipefail

COMPOSE_DIR=${COMPOSE_DIR:-/opt/cyberpaw}
compose() { docker compose --project-directory "$COMPOSE_DIR" "$@"; }

compose exec -T -u root web rm -rf /tmp/cyberpaw-seed
compose exec -T -u root web mkdir -p /tmp/cyberpaw-seed
compose cp scripts/seed_demo.py web:/tmp/cyberpaw-seed/seed_demo.py
compose cp scripts/platform_api.py web:/tmp/cyberpaw-seed/platform_api.py
# docker cp keeps the host file modes; make them readable by the app user.
compose exec -T -u root web chmod -R a+rX /tmp/cyberpaw-seed
compose exec -T web python /tmp/cyberpaw-seed/seed_demo.py "$@" 2>&1 | grep -vE "Loaded module|alembic|SAWarning|session.commit|synchronize_session|filter_by\(id"
compose exec -T -u root web rm -rf /tmp/cyberpaw-seed
