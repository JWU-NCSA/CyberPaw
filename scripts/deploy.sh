#!/bin/bash
# Deploy a commit of JWU-NCSA/CyberPaw that is on main and passed CI.
#
#   On the staging VM:    sudo bash scripts/deploy.sh staging           the latest main
#   On the production VM: sudo bash scripts/deploy.sh promote <commit>  the commit tested on staging
#
# Run from /opt/cyberpaw/repo. The server only reads from GitHub; GitHub never connects to the server.
# The deployed commit is written to /opt/cyberpaw/deployed.
set -euo pipefail

REPO=JWU-NCSA/CyberPaw
COMPOSE_DIR=${COMPOSE_DIR:-/opt/cyberpaw}
REPO_DIR=$COMPOSE_DIR/repo
# Check runs that must have passed on the commit (.github/workflows).
REQUIRED_CHECKS="checks smoke-test gitleaks"

compose() { docker compose --project-directory "$COMPOSE_DIR" "$@"; }
fail() { echo "deploy: $*" >&2; exit 1; }

ci_passed() {
  curl -fsSL -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/commits/$1/check-runs?per_page=100" |
    REQUIRED_CHECKS="$REQUIRED_CHECKS" python3 -c '
import json, os, sys
runs = json.load(sys.stdin)["check_runs"]
bad = []
for name in os.environ["REQUIRED_CHECKS"].split():
    mine = sorted((r for r in runs if r["name"] == name), key=lambda r: r["started_at"] or "")
    result = mine[-1]["conclusion"] if mine else "missing"
    if result != "success":
        bad.append(f"{name}: {result}")
if bad:
    print("CI has not passed on this commit (" + ", ".join(bad) + ")", file=sys.stderr)
    sys.exit(1)
'
}

# Everything runs from main(), so bash has read the whole script before git checkout replaces this file.
main() {
  [ "$(id -u)" = 0 ] || fail "run with sudo"
  local mode=${1:-} target=${2:-}
  cd "$REPO_DIR"
  git fetch -q origin main

  local sha
  case "$mode" in
    staging) sha=$(git rev-parse origin/main) ;;
    promote)
      [ -n "$target" ] || fail "usage: deploy.sh promote <commit> (the commit staging printed)"
      sha=$(git rev-parse --verify -q "$target^{commit}") || fail "unknown commit $target"
      ;;
    *) fail "usage: deploy.sh staging | promote <commit>" ;;
  esac
  git merge-base --is-ancestor "$sha" origin/main || fail "$sha is not on main"
  ci_passed "$sha" || fail "refusing to deploy $sha"

  local previous
  previous=$(git rev-parse HEAD)
  echo "Deploying $(git log -1 --format='%h %s' "$sha")"
  git checkout -q --detach "$sha"
  if ! cmp -s config/docker-compose.yml "$COMPOSE_DIR/docker-compose.yml"; then
    cp "$COMPOSE_DIR/docker-compose.yml" "$COMPOSE_DIR/docker-compose.yml.previous"
    cp config/docker-compose.yml "$COMPOSE_DIR/"
    echo "docker-compose.yml changed (old copy: $COMPOSE_DIR/docker-compose.yml.previous)"
  fi
  compose up -d --quiet-pull
  # The plugin's Python is only loaded at start.
  compose restart web
  local ok=""
  for _ in $(seq 60); do
    if [ "$(curl -s http://127.0.0.1/healthcheck)" = OK ]; then ok=1; break; fi
    sleep 2
  done
  [ -n "$ok" ] || fail "site did not come back. Logs: sudo docker compose --project-directory $COMPOSE_DIR logs web
To go back: sudo git -C $REPO_DIR checkout --detach $previous, then run the compose and apply-config steps"
  bash scripts/apply-config.sh "$COMPOSE_DIR"
  printf '%s %s %s\n' "$sha" "$mode" "$(date -u +%FT%TZ)" > "$COMPOSE_DIR/deployed"

  echo "Deployed $sha ($mode)."
  if [ "$mode" = staging ]; then
    echo "Check https://staging.jwucyberlab.org, then on the production VM:"
    echo "  cd $REPO_DIR && sudo bash scripts/deploy.sh promote $sha"
  fi
}

main "$@"
