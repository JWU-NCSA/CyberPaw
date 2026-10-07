#!/bin/bash
# Apply CyberPaw settings and branding to the running site.
# Run on the server from the repo root: sudo scripts/apply-config.sh [compose_dir]
set -euo pipefail

COMPOSE_DIR=${1:-/opt/cyberpaw}
# The staging VM has an empty file named "staging" next to docker-compose.yml (never on production).
STAGING_FLAG=""
[ -f "$COMPOSE_DIR/staging" ] && STAGING_FLAG=--staging
compose() { docker compose --project-directory "$COMPOSE_DIR" "$@"; }

compose exec -T -u root web rm -rf /tmp/cyberpaw
compose cp theme web:/tmp/cyberpaw
compose cp scripts/apply_config.py web:/tmp/cyberpaw/apply_config.py
compose cp scripts/platform_api.py web:/tmp/cyberpaw/platform_api.py
# docker cp keeps the host file modes; make them readable by the app user.
compose exec -T -u root web chmod -R a+rX /tmp/cyberpaw
compose exec -T web python /tmp/cyberpaw/apply_config.py /tmp/cyberpaw $STAGING_FLAG 2>&1 | grep -vE "Loaded module|alembic"
compose exec -T -u root web rm -rf /tmp/cyberpaw
