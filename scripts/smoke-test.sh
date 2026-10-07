#!/bin/bash
# Start the whole site from this checkout (config/docker-compose.yml with throwaway secrets), apply the
# CyberPaw config and check the main pages. Used by CI (.github/workflows/ci.yml); also runs on any machine
# with Docker, from the repo root: bash scripts/smoke-test.sh
# Leaves the stack running; remove it with: docker compose --project-directory config down -v
set -euo pipefail

B=http://127.0.0.1
JAR=$(mktemp)
COMPOSE_DIR=$PWD/config
compose() { docker compose --project-directory "$COMPOSE_DIR" "$@"; }
fail() { echo "FAIL: $*" >&2; compose logs web | tail -40 >&2; exit 1; }
nonce() { curl -s -c "$JAR" -b "$JAR" "$B$1" | grep -oP "csrfNonce.: \"\K[^\"]+"; }
# POST a form and print the redirect target (path only).
post() {
  local url=$1; shift
  curl -s -o /dev/null -w "%{redirect_url}" -c "$JAR" -b "$JAR" -X POST "$B$url" "$@" | sed "s#^$B##"
}
api_config() {
  curl -sf -o /dev/null -c "$JAR" -b "$JAR" -X PATCH "$B/api/v1/configs" -H "Content-Type: application/json" \
    -H "CSRF-Token: $(nonce /)" -d "$1" || fail "config update $1"
}

if [ ! -f "$COMPOSE_DIR/.env" ]; then
  umask 077
  printf 'SECRET_KEY=%s\nDB_PASSWORD=%s\nDB_ROOT_PASSWORD=%s\nREPO_DIR=%s\nWORKERS=1\n' \
    "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$PWD" > "$COMPOSE_DIR/.env"
  umask 022
fi
compose up -d --quiet-pull
for _ in $(seq 90); do [ "$(curl -s $B/healthcheck)" = OK ] && break; sleep 2; done
[ "$(curl -s $B/healthcheck)" = OK ] || fail "site did not start"

echo "== setup and CyberPaw config"
N=$(nonce /setup)
post /setup --data-urlencode ctf_name=Test --data-urlencode ctf_description=test --data-urlencode user_mode=users \
  --data-urlencode name=admin --data-urlencode email=admin@jwu.edu --data-urlencode password=SmokeTest-Admin-1 \
  --data-urlencode ctf_theme=core-beta --data-urlencode challenge_visibility=private \
  --data-urlencode account_visibility=public --data-urlencode score_visibility=public \
  --data-urlencode registration_visibility=public --data-urlencode verify_emails= --data-urlencode team_size= \
  --data-urlencode start= --data-urlencode end= --data-urlencode "nonce=$N" >/dev/null
bash scripts/apply-config.sh "$COMPOSE_DIR" | tail -1 | grep -q "Applied CyberPaw config" || fail "apply-config"

echo "== admin pages"
N=$(nonce /login)
post /login --data-urlencode name=admin --data-urlencode password=SmokeTest-Admin-1 --data-urlencode "nonce=$N" >/dev/null
for page in /admin/cyberpaw /admin/config; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" $B$page)" = 200 ] || fail "$page"
done
# Competition starts in 5 days; no email confirmation (there is no mail server here).
api_config "{\"start\": $(( $(date +%s) + 5 * 86400 )), \"verify_emails\": false}"
curl -s -o /dev/null -c "$JAR" -b "$JAR" $B/logout

echo "== guest"
curl -s $B/ | grep -q 'cp-home' || fail "home page"
[ "$(curl -s -o /dev/null -w '%{redirect_url}' $B/challenges | sed "s#^$B##")" = "/login?next=%2Fchallenges" ] \
  || fail "guest /challenges should go to login"

echo "== player"
N=$(nonce "/register?ref=1")
post /register --data-urlencode name=player1 --data-urlencode email=player1@jwu.edu \
  --data-urlencode password=SmokeTest-Player-1 --data-urlencode "nonce=$N" >/dev/null
curl -s -o /dev/null -c "$JAR" -b "$JAR" $B/logout
N=$(nonce /login)
landing=$(post /login --data-urlencode name=player1 --data-urlencode password=SmokeTest-Player-1 --data-urlencode "nonce=$N")
[ "$landing" = / ] || fail "login should land on /, got $landing"
curl -s -b "$JAR" $B/ | grep -q 'id="cp-referral-link"' || fail "invite link on home page"
curl -s -b "$JAR" $B/settings | grep -q 'id="cp-referral-link"' || fail "invite link on settings"
page=$(curl -s -w '\n%{http_code}' -b "$JAR" $B/challenges)
[ "$(tail -1 <<<"$page")" = 200 ] && grep -q 'data-cp-status' <<<"$page" || fail "/challenges countdown before start"
for path in /scoreboard /users /rules /how-to-play /credits /confirm; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" $B$path)
  case "$code" in 200|302) ;; *) fail "$path returned $code" ;; esac
done

if compose logs web | grep -q Traceback; then fail "errors in the web log"; fi
echo "Smoke test passed"
