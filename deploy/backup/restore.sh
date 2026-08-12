#!/usr/bin/env bash
#
# Restore the database from a backup.
#
# Read this before you need it. The worst moment to first read a restore script
# is during the incident that requires it.
#
#   ./restore.sh --list                       what is available
#   ./restore.sh --latest --into scratch_db   rehearse (do this monthly)
#   ./restore.sh --key hourly/... --confirm-production-overwrite
#
# The default target is a scratch database, and overwriting production needs an
# explicit flag with an unmissable name. A restore script whose easy path
# destroys the live database is a script that will eventually destroy the live
# database.

set -Eeuo pipefail

: "${BACKUP_S3_BUCKET:?}" "${PGDATABASE:?}"

TARGET=""
KEY=""
LATEST=0
LIST=0
OVERWRITE_PROD=0

s3() {
  if [[ -n "${BACKUP_S3_ENDPOINT:-}" ]]; then aws --endpoint-url "$BACKUP_S3_ENDPOINT" "$@"; else aws "$@"; fi
}
log() { printf '%s restore: %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)   LIST=1; shift ;;
    --latest) LATEST=1; shift ;;
    --key)    KEY="$2"; shift 2 ;;
    --into)   TARGET="$2"; shift 2 ;;
    --confirm-production-overwrite) OVERWRITE_PROD=1; shift ;;
    *) die "unknown argument: $1" ;;
  esac
done

if (( LIST )); then
  log "backups in s3://${BACKUP_S3_BUCKET}/hourly/"
  s3 s3 ls "s3://${BACKUP_S3_BUCKET}/hourly/" --human-readable | sort -r | head -50
  exit 0
fi

if (( LATEST )); then
  KEY=$(s3 s3 ls "s3://${BACKUP_S3_BUCKET}/hourly/" | sort | tail -1 | awk '{print $4}')
  [[ -n "$KEY" ]] || die "no backups found"
  KEY="hourly/${KEY}"
fi
[[ -n "$KEY" ]] || die "specify --key or --latest (or --list to see what exists)"

if (( OVERWRITE_PROD )); then
  TARGET="$PGDATABASE"
  # A typed confirmation, not a y/n. Muscle memory answers y.
  log "This will DROP AND REPLACE the production database '${PGDATABASE}'."
  log "Every write since ${KEY} was taken will be lost."
  read -r -p "Type the database name to proceed: " typed
  [[ "$typed" == "$PGDATABASE" ]] || die "aborted"
else
  TARGET="${TARGET:-restore_scratch}"
  log "Restoring into '${TARGET}'. Production is untouched."
  log "(Use --confirm-production-overwrite only when you mean it.)"
fi

readonly ENCRYPTED="/tmp/$(basename "$KEY")"
readonly DUMP="${ENCRYPTED%.age}"
trap 'rm -f "$ENCRYPTED" "$DUMP"' EXIT

log "downloading ${KEY}"
s3 s3 cp "s3://${BACKUP_S3_BUCKET}/${KEY}" "$ENCRYPTED" --only-show-errors

# The identity file is NOT on this host in normal operation — that is the point
# of encrypting. Mount it for the restore and remove it afterwards.
[[ -f "${AGE_IDENTITY_FILE:-/run/secrets/age_identity}" ]] \
  || die "no age identity at ${AGE_IDENTITY_FILE:-/run/secrets/age_identity}. It is kept off this host deliberately — mount it to restore."

log "decrypting"
age --decrypt --identity "${AGE_IDENTITY_FILE:-/run/secrets/age_identity}" \
    --output "$DUMP" "$ENCRYPTED"

if (( OVERWRITE_PROD )); then
  # Terminate first. `dropdb` fails while anything holds a connection, and
  # during an incident everything is reconnecting in a loop.
  log "disconnecting clients"
  psql -d postgres -c "
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
     WHERE datname = '${TARGET}' AND pid <> pg_backend_pid();" >/dev/null
  dropdb --if-exists "$TARGET"
fi

createdb "$TARGET" 2>/dev/null || log "database ${TARGET} already exists — restoring into it"

log "restoring (parallel, 4 jobs)"
# --clean --if-exists so a restore into a non-empty database replaces rather
# than colliding. -j4 is most of why this is minutes and not hours.
pg_restore \
  --dbname="$TARGET" \
  --no-owner --no-privileges \
  --clean --if-exists \
  --jobs=4 \
  --exit-on-error \
  "$DUMP"

log "verifying"
psql -d "$TARGET" -tA -c "
  SELECT 'users:      ' || count(*) FROM users
  UNION ALL SELECT 'properties: ' || count(*) FROM properties
  UNION ALL SELECT 'bookings:   ' || count(*) FROM bookings
  UNION ALL SELECT 'payments:   ' || count(*) FROM payments;"

log "restored ${KEY} into ${TARGET}"
if (( ! OVERWRITE_PROD )); then
  log "Drop it when finished:  dropdb ${TARGET}"
fi
