#!/usr/bin/env bash
#
# First-boot TLS. Run once, on a fresh host, before `docker compose up`.
#
# The chicken-and-egg this solves: nginx will not start without a certificate
# file, and Certbot cannot obtain one without nginx answering the ACME
# challenge on port 80. So a throwaway self-signed pair goes down first, nginx
# starts, the real certificate replaces it, and nginx reloads.
#
# Renewal is *not* handled here — the `certbot` service in the compose file
# wakes every twelve hours and renews anything inside thirty days of expiry.
# This script is for the very first certificate only, and is safe to re-run:
# it detects an existing live certificate and stops.

set -Eeuo pipefail

readonly DOMAINS=(
  roamingwandering.com
  www.roamingwandering.com
  admin.roamingwandering.com
  host.roamingwandering.com
)
readonly PRIMARY="${DOMAINS[0]}"
readonly EMAIL="${CERTBOT_EMAIL:?set CERTBOT_EMAIL — expiry warnings go here}"
readonly COMPOSE="docker compose -f docker-compose.prod.yml"

# Let's Encrypt allows five duplicate certificates per week. A staging run
# first is how you avoid burning that allowance on a typo'd domain and then
# waiting seven days.
STAGING="${STAGING:-1}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f docker-compose.prod.yml ]] || die "run this from deploy/"

if $COMPOSE run --rm --entrypoint sh certbot -c \
     "[ -d /etc/letsencrypt/live/$PRIMARY ]" 2>/dev/null; then
  log "A certificate for $PRIMARY already exists. Nothing to do."
  log "To replace it deliberately: $COMPOSE run --rm certbot delete --cert-name $PRIMARY"
  exit 0
fi

# ── 1. a placeholder, so nginx can start ──────────────────────────────────
#
# 1024-bit and one day: it exists only to let nginx bind 443 for the few
# seconds before the real one arrives, and a short-lived weak key that is
# overwritten in the same script is not a key anyone will forget to rotate.
log "Creating a temporary self-signed certificate"
$COMPOSE run --rm --entrypoint sh certbot -c "
  mkdir -p /etc/letsencrypt/live/$PRIMARY &&
  openssl req -x509 -nodes -newkey rsa:1024 -days 1 \
    -keyout /etc/letsencrypt/live/$PRIMARY/privkey.pem \
    -out    /etc/letsencrypt/live/$PRIMARY/fullchain.pem \
    -subj   '/CN=localhost' 2>/dev/null &&
  cp /etc/letsencrypt/live/$PRIMARY/fullchain.pem \
     /etc/letsencrypt/live/$PRIMARY/chain.pem"

log "Starting nginx so it can answer the ACME challenge"
$COMPOSE up -d nginx
# nginx binds fast, but a container that is 'up' is not always listening.
for _ in $(seq 1 30); do
  curl -fsS -o /dev/null "http://localhost/.well-known/acme-challenge/probe" 2>/dev/null && break
  # 404 is a fine answer — it means nginx is serving that path.
  curl -fsS -o /dev/null -w '%{http_code}' "http://localhost/" 2>/dev/null | grep -q . && break
  sleep 1
done

# ── 2. the real certificate ───────────────────────────────────────────────
log "Removing the placeholder"
$COMPOSE run --rm --entrypoint sh certbot -c \
  "rm -rf /etc/letsencrypt/live/$PRIMARY /etc/letsencrypt/archive/$PRIMARY \
          /etc/letsencrypt/renewal/$PRIMARY.conf"

domain_args=()
for domain in "${DOMAINS[@]}"; do domain_args+=(-d "$domain"); done

staging_arg=()
if [[ "$STAGING" != "0" ]]; then
  staging_arg=(--staging)
  log "STAGING run — the certificate will NOT be trusted by browsers."
  log "Once this succeeds, re-run with STAGING=0 for the real thing."
fi

log "Requesting a certificate for: ${DOMAINS[*]}"
$COMPOSE run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  "${staging_arg[@]}" \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  --rsa-key-size 4096 \
  --force-renewal \
  "${domain_args[@]}" \
  || die "Certbot failed. Common causes: DNS not yet pointing here, port 80 blocked upstream, or a domain in the list with no A record."

log "Reloading nginx"
$COMPOSE exec nginx nginx -s reload

if [[ "$STAGING" != "0" ]]; then
  log "Staging certificate installed. Re-run with STAGING=0 to go live:"
  log "    STAGING=0 CERTBOT_EMAIL=$EMAIL ./certbot/init-letsencrypt.sh"
else
  log "Done. Renewal is automatic — the certbot service checks twice a day."
  log "Verify externally: https://www.ssllabs.com/ssltest/analyze.html?d=$PRIMARY"
fi
