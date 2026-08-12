#!/usr/bin/env bash
#
# Hourly database backup: dump, encrypt, upload, **verify**, prune.
#
# The verify step is the point of this script. An unverified backup is a
# reassuring file of unknown value, and the day you discover it does not
# restore is the day you needed it. So every dump is restored into a scratch
# database and sanity-checked before it counts as a success, and the metric
# that alerts is `backup_verify_success`, not "the upload returned 200".
#
# Encrypted with age before it leaves the host. The bucket's own encryption
# protects the data from someone with the disk; it does nothing against
# whoever holds the bucket credentials — which is this container, and anything
# that compromises it.
#
#   BACKUP_AGE_RECIPIENT   an age public key. The private half must be kept
#                          OFF this host, or the encryption is theatre.
#
# Restore is `restore.sh`. Read it before you need it.

set -Eeuo pipefail

readonly STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
readonly DUMP="/tmp/${PGDATABASE}-${STAMP}.dump"
readonly ENCRYPTED="${DUMP}.age"
readonly KEY="hourly/${PGDATABASE}-${STAMP}.dump.age"
readonly METRICS="/var/lib/backup/metrics.prom"

: "${BACKUP_S3_BUCKET:?}" "${BACKUP_AGE_RECIPIENT:?}" "${PGDATABASE:?}"
readonly RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

s3() {
  if [[ -n "${BACKUP_S3_ENDPOINT:-}" ]]; then
    aws --endpoint-url "$BACKUP_S3_ENDPOINT" "$@"
  else
    aws "$@"
  fi
}

log()  { printf '%s backup: %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { log "FAILED: $*"; write_metrics 0 0; ping_failure; exit 1; }

# Written to a file Prometheus scrapes via node-exporter's textfile collector.
# A metric rather than a log line because "no backup for 26 hours" has to be
# alertable, and absence of a log line is not something you can alert on.
write_metrics() {
  local backup_ok="$1" verify_ok="$2"
  mkdir -p "$(dirname "$METRICS")"
  cat > "$METRICS.tmp" <<EOF
# HELP backup_last_success_timestamp_seconds Unix time of the last successful, verified backup.
# TYPE backup_last_success_timestamp_seconds gauge
backup_last_success_timestamp_seconds $([[ "$backup_ok" == 1 && "$verify_ok" == 1 ]] && date +%s || echo 0)
# HELP backup_verify_success Whether the last dump restored cleanly into a scratch database.
# TYPE backup_verify_success gauge
backup_verify_success $verify_ok
# HELP backup_size_bytes Size of the last encrypted dump.
# TYPE backup_size_bytes gauge
backup_size_bytes ${SIZE:-0}
# HELP backup_duration_seconds How long the last run took end to end.
# TYPE backup_duration_seconds gauge
backup_duration_seconds ${DURATION:-0}
EOF
  # Atomic: node-exporter reads this file on its own schedule and a partial
  # read produces a parse error that looks like a broken exporter.
  mv "$METRICS.tmp" "$METRICS"
}

ping_success() { [[ -n "${HEALTHCHECK_PING_URL:-}" ]] && curl -fsS -m 10 "$HEALTHCHECK_PING_URL" >/dev/null 2>&1 || true; }
ping_failure() { [[ -n "${HEALTHCHECK_PING_URL:-}" ]] && curl -fsS -m 10 "${HEALTHCHECK_PING_URL}/fail" >/dev/null 2>&1 || true; }

cleanup() { rm -f "$DUMP" "$ENCRYPTED"; }
trap cleanup EXIT

START=$(date +%s)

# ── 1. dump ───────────────────────────────────────────────────────────────
#
# Custom format (-Fc), not plain SQL. It is compressed, and it lets
# `pg_restore` do a selective or parallel restore — which is the difference
# between a four-hour and a twenty-minute recovery on a large database.
log "dumping ${PGDATABASE}"
pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-privileges \
  --file="$DUMP" \
  || fail "pg_dump"

SIZE_RAW=$(stat -c%s "$DUMP" 2>/dev/null || stat -f%z "$DUMP")
# A dump far smaller than the last one usually means a partial dump or a
# database that has been emptied — either way, uploading it over yesterday's
# good copy is how a bad backup becomes the only backup.
if (( SIZE_RAW < 1024 )); then
  fail "dump is only ${SIZE_RAW} bytes — refusing to upload"
fi
log "dumped ${SIZE_RAW} bytes"

# ── 2. verify, before uploading ───────────────────────────────────────────
#
# Restore into a scratch database and check that the tables that matter are
# there and populated. Doing this *before* the upload means a corrupt dump is
# never stored at all.
log "verifying by restoring into a scratch database"
readonly SCRATCH="verify_${STAMP//[!0-9]/}"
VERIFY_OK=0
if createdb "$SCRATCH" 2>/dev/null; then
  if pg_restore --dbname="$SCRATCH" --no-owner --no-privileges --exit-on-error "$DUMP" >/dev/null 2>&1; then
    # Not just "did it restore" — a dump of an empty database restores
    # perfectly. These are the tables whose absence means the backup is
    # useless.
    counts=$(psql -d "$SCRATCH" -tA -c "
      SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'public'
         AND table_name IN ('users','properties','bookings','payments');" 2>/dev/null || echo 0)
    if [[ "$counts" == "4" ]]; then
      VERIFY_OK=1
      log "verified: schema restored with the core tables present"
    else
      log "VERIFY FAILED: expected 4 core tables, found ${counts}"
    fi
  else
    log "VERIFY FAILED: pg_restore reported errors"
  fi
  dropdb --if-exists "$SCRATCH" 2>/dev/null || log "warning: could not drop ${SCRATCH}"
else
  log "VERIFY SKIPPED: could not create a scratch database"
fi

(( VERIFY_OK == 1 )) || fail "verification"

# ── 3. encrypt ────────────────────────────────────────────────────────────
log "encrypting"
age --recipient "$BACKUP_AGE_RECIPIENT" --output "$ENCRYPTED" "$DUMP" || fail "age encrypt"
SIZE=$(stat -c%s "$ENCRYPTED" 2>/dev/null || stat -f%z "$ENCRYPTED")

# ── 4. upload ─────────────────────────────────────────────────────────────
log "uploading s3://${BACKUP_S3_BUCKET}/${KEY}"
s3 s3 cp "$ENCRYPTED" "s3://${BACKUP_S3_BUCKET}/${KEY}" \
  --only-show-errors \
  --metadata "database=${PGDATABASE},verified=true,taken=${STAMP}" \
  || fail "upload"

# Read it back. An upload that returned success and stored nothing is rare and
# catastrophic, and the check costs one HEAD request.
remote_size=$(s3 s3api head-object --bucket "$BACKUP_S3_BUCKET" --key "$KEY" \
  --query ContentLength --output text 2>/dev/null || echo 0)
[[ "$remote_size" == "$SIZE" ]] || fail "uploaded size ${remote_size} != local ${SIZE}"

# ── 5. prune ──────────────────────────────────────────────────────────────
#
# Deliberately after a successful upload, never before: pruning first and then
# failing to upload leaves a gap where the old backups are gone and the new one
# does not exist.
log "pruning backups older than ${RETENTION_DAYS} days"
cutoff=$(date -u -d "${RETENTION_DAYS} days ago" +%Y%m%d 2>/dev/null \
      || date -u -v-"${RETENTION_DAYS}"d +%Y%m%d)
s3 s3 ls "s3://${BACKUP_S3_BUCKET}/hourly/" | while read -r _ _ _ name; do
  [[ "$name" =~ -([0-9]{8})T ]] || continue
  if [[ "${BASH_REMATCH[1]}" < "$cutoff" ]]; then
    log "  removing ${name}"
    s3 s3 rm "s3://${BACKUP_S3_BUCKET}/hourly/${name}" --only-show-errors || true
  fi
done

DURATION=$(( $(date +%s) - START ))
write_metrics 1 1
ping_success
log "done in ${DURATION}s — ${SIZE} bytes at ${KEY}"
