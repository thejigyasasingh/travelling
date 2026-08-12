#!/usr/bin/env bash
#
# Generate the JWT signing pair.
#
# RS256 rather than HS256, and the reason is operational rather than
# cryptographic: with a shared secret, anything that *verifies* a token can
# also *mint* one. An asymmetric pair means a future service — a mobile BFF, an
# analytics job — can be given the public half and verify tokens without being
# able to forge them.
#
# Run once per environment. The private key never leaves the host it is
# generated on and is never committed; `deploy/secrets/` is gitignored.

set -Eeuo pipefail
readonly DIR="${1:-./secrets}"
mkdir -p "$DIR"

if [[ -f "$DIR/jwt_private_key.pem" ]]; then
  echo "A key already exists at $DIR/jwt_private_key.pem."
  echo "Replacing it invalidates every access token in circulation — every"
  echo "signed-in user is logged out. Delete it by hand if that is intended."
  exit 1
fi

# 2048 is the floor; 4096 costs a little more per verification and is the
# sensible default for a key with a multi-year life.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
  -out "$DIR/jwt_private_key.pem" 2>/dev/null
openssl rsa -pubout -in "$DIR/jwt_private_key.pem" \
  -out "$DIR/jwt_public_key.pem" 2>/dev/null

# 600 on the private key. Docker mounts it into the container as-is, and a
# world-readable signing key on a shared host is a forged-token factory.
chmod 600 "$DIR/jwt_private_key.pem"
chmod 644 "$DIR/jwt_public_key.pem"

echo "Wrote:"
echo "  $DIR/jwt_private_key.pem  (600 — never commit, never copy off this host)"
echo "  $DIR/jwt_public_key.pem   (644)"
echo
echo "Back up the private key somewhere offline. Losing it does not lose data,"
echo "but it does sign every user out at once."
