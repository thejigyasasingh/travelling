#!/usr/bin/env bash
#
# Deploy a tag.
#
#   ./scripts/deploy.sh 1a2b3c4
#   ./scripts/deploy.sh --rollback
#
# What this does that `docker compose up -d` does not:
#
#   * **pulls before stopping anything.** A failed pull halfway through leaves
#     the old version running rather than a half-updated stack.
#   * **runs migrations as their own step**, and aborts the deploy if they
#     fail — rather than starting an API against a schema it does not expect.
#   * **waits for readiness** before declaring success, and rolls back if the
#     new version never becomes ready.
#   * **records the tag it replaced**, so `--rollback` is one command at 3am
#     rather than an archaeology exercise.
#
# What it does not do: zero-downtime. This is a single host, and the API
# restart is a few seconds of drain — `stop_grace_period` lets in-flight
# requests finish. If that is not acceptable, the answer is a second host and a
# load balancer, not a cleverer script.

set -Eeuo pipefail
cd "$(dirname "$0")/.."

readonly COMPOSE="docker compose -f docker-compose.prod.yml"
readonly STATE=".deploy-state"
readonly ENV_FILE=".env"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || die "no .env — copy env/production.env.example and fill it in"
[[ -f secrets/jwt_private_key.pem ]] || die "no JWT key — run ./scripts/gen-jwt-keys.sh"

current_tag() { grep -E '^TAG=' "$ENV_FILE" | cut -d= -f2- ; }

# ── rollback ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--rollback" ]]; then
  [[ -f "$STATE" ]] || die "no previous deployment recorded"
  previous=$(grep -E '^previous_tag=' "$STATE" | cut -d= -f2-)
  [[ -n "$previous" ]] || die "no previous tag in $STATE"

  warn "Rolling back to ${previous}."
  warn "This rolls back CODE ONLY. Migrations are not reversed — if the"
  warn "deployment you are undoing changed the schema, the old code may not"
  warn "run against it. Check the migration before continuing."
  read -r -p "Continue? [y/N] " reply
  [[ "$reply" == "y" ]] || exit 1

  sed -i.bak "s/^TAG=.*/TAG=${previous}/" "$ENV_FILE"
  $COMPOSE up -d --no-deps api worker beat web admin vendor
  log "Rolled back to ${previous}"
  exit 0
fi

readonly TAG="${1:?usage: deploy.sh <tag> | --rollback}"
readonly PREVIOUS="$(current_tag)"

[[ "$TAG" != "latest" ]] || die "refusing to deploy 'latest' — use an immutable tag"

log "Deploying ${TAG} (currently ${PREVIOUS:-none})"

# ── 1. pull everything first ──────────────────────────────────────────────
#
# Before touching the running stack. A missing image or an expired registry
# credential should fail here, with the old version still serving.
log "Pulling images"
TAG="$TAG" $COMPOSE pull --quiet api web admin vendor \
  || die "pull failed — the running version is untouched"

# ── 2. migrate ────────────────────────────────────────────────────────────
#
# Its own step so a failure is unambiguous. Alembic takes an advisory lock, so
# this is safe even if something else is mid-migration.
log "Running migrations"
sed -i.bak "s/^TAG=.*/TAG=${TAG}/" "$ENV_FILE"
if ! $COMPOSE run --rm migrate; then
  warn "Migrations failed. Reverting TAG; nothing was restarted."
  sed -i.bak "s/^TAG=.*/TAG=${PREVIOUS}/" "$ENV_FILE"
  die "migration failure"
fi

# ── 3. restart the application ────────────────────────────────────────────
#
# `--no-deps` so Postgres and Redis are not restarted. Restarting a database
# to deploy application code is how a deploy becomes an outage.
log "Restarting services"
$COMPOSE up -d --no-deps api worker beat web admin vendor

# ── 4. wait for readiness ─────────────────────────────────────────────────
#
# Readiness, not liveness: liveness answers before the database pool is warm,
# and a "successful" deploy that immediately 503s is worse than a failed one.
log "Waiting for readiness"
ready=0
for attempt in $(seq 1 60); do
  if $COMPOSE exec -T api curl -fsS http://localhost:8000/health/ready >/dev/null 2>&1; then
    ready=1
    log "Ready after ${attempt}s"
    break
  fi
  sleep 1
done

if (( ! ready )); then
  warn "The new version never became ready. Rolling back."
  sed -i.bak "s/^TAG=.*/TAG=${PREVIOUS}/" "$ENV_FILE"
  $COMPOSE up -d --no-deps api worker beat web admin vendor
  die "deploy failed — rolled back to ${PREVIOUS}. Logs: $COMPOSE logs --tail=200 api"
fi

# ── 5. record, and tidy ───────────────────────────────────────────────────
cat > "$STATE" <<EOF
# Written by deploy.sh. Read by --rollback.
deployed_tag=${TAG}
previous_tag=${PREVIOUS}
deployed_at=$(date -u +%FT%TZ)
deployed_by=${USER:-unknown}
EOF
rm -f "${ENV_FILE}.bak"

# Old images accumulate until the disk fills, which is a Postgres outage by
# another route. `--filter until=168h` keeps a week, so a rollback further back
# than that needs a pull rather than failing outright.
log "Pruning images older than a week"
docker image prune -af --filter "until=168h" >/dev/null 2>&1 || true

log "Deployed ${TAG}"
log "Roll back with: ./scripts/deploy.sh --rollback"
