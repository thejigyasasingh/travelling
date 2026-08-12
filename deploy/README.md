# Deploying Roaming & Wandering

Everything needed to run this in production, and the reasoning behind the
choices that are not obvious. Read [Architecture](#architecture) once; the rest
is reference.

---

## Architecture

A single host running Docker Compose. Nine application containers, three data
containers, seven for observability.

```
                    ┌─────────────┐
   internet ────────▶    nginx     │  TLS, rate limits, security headers
                    └──────┬──────┘
             ┌─────────────┼─────────────┬─────────────┐
             ▼             ▼             ▼             ▼
          ┌──────┐    ┌────────┐   ┌────────┐   ┌────────┐
          │ web  │    │ admin  │   │ vendor │   │  api   │
          └──────┘    └────────┘   └────────┘   └───┬────┘
                                                    │
                              ┌─────────────────────┼──────────┐
                              ▼                     ▼          ▼
                        ┌──────────┐          ┌─────────┐  ┌────────┐
                        │ postgres │◀─────────│  redis  │  │ worker │
                        └────┬─────┘          └─────────┘  │  beat  │
                             │                             └────────┘
                        ┌────▼─────┐
                        │  backup  │ ─── hourly, encrypted, off-host
                        └──────────┘
```

### Why Compose and not Kubernetes

This is one product with four processes and a database. Compose runs it on one
machine with an hour of setup, and the entire operational surface is a file you
can read in one sitting. Kubernetes solves problems this deployment does not
have and introduces failure modes it does not need.

What that costs, stated plainly so nobody discovers it mid-incident:

- **A deploy restarts the API.** `stop_grace_period: 45s` drains in-flight
  requests and `deploy.sh` waits for readiness, so it is a few seconds, not an
  outage. There is no rolling update across nodes.
- **The host is a single point of failure.** Hourly verified backups to
  off-host storage are the recovery story. Recovery time is however long it
  takes to provision a machine and run `restore.sh` — rehearse it (below) so
  you know that number before you need it.

Move to Kubernetes when you need a second node. Not before.

### Three networks

The split is the security boundary, not organisation.

| Network | Contains | Reachable from outside |
|---|---|---|
| `edge` | nginx, the three static apps, the API | via nginx only |
| `internal` | API, worker, beat, postgres, redis, backup | **no** (`internal: true`) |
| `observe` | prometheus, grafana, loki, exporters | **no** |

**Postgres and Redis publish no ports.** A `ports:` line on either is the most
common way a database ends up on the public internet, and
`.github/workflows/security.yml` fails the build if one appears.

### Why the API is same-origin

The API is mounted at `/api/` on each front-end host rather than on its own
subdomain. The refresh token is the reason: it is an HttpOnly cookie scoped to
`/api/v1/auth`, and a cross-origin API host would need `SameSite=None` to send
it — which is exactly what CSRF protection exists to avoid. Same origin means
`SameSite=Lax` and the browser closes the whole class of attack.

---

## First deployment

Assumes Ubuntu 24.04, a domain, and DNS already pointing at the host.

### 1. Host

```bash
# Docker, from Docker's repository — the distribution package lags badly.
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" && newgrp docker

# Only 22, 80 and 443. Everything else is on an internal network and Docker
# writes its own iptables rules — which is why `ufw deny 5432` does NOT
# protect Postgres. Not publishing the port is what protects Postgres.
sudo ufw default deny incoming && sudo ufw allow 22,80,443/tcp && sudo ufw enable

sudo mkdir -p /srv/roaming-wandering && sudo chown "$USER" /srv/roaming-wandering
git clone <repo> /srv/roaming-wandering
cd /srv/roaming-wandering/deploy
```

### 2. Secrets

```bash
./scripts/gen-jwt-keys.sh          # writes secrets/, gitignored, 600

cp env/production.env.example .env
chmod 600 .env
```

Fill in `.env`. Generate every password with `openssl rand -base64 36` — a
password someone chose is a password someone can guess.

**The backup encryption key needs care:**

```bash
age-keygen -o age-key.txt          # do this on your LAPTOP, not the server
```

Put the **public** key in `BACKUP_AGE_RECIPIENT`. Store the **private** half in
a password manager and delete it from the host. Encrypting a backup with a key
kept beside it is not encryption — it is a checkbox.

### 3. TLS

```bash
STAGING=1 CERTBOT_EMAIL=ops@example.com ./certbot/init-letsencrypt.sh
```

Staging first, always. Let's Encrypt allows five duplicate certificates per
week; a typo in a domain burns one and you wait. When the staging run succeeds:

```bash
STAGING=0 CERTBOT_EMAIL=ops@example.com ./certbot/init-letsencrypt.sh
```

Renewal is automatic — the `certbot` container checks twice a day and nginx
reloads every six hours to pick up a renewed file.

### 4. Up

```bash
./scripts/deploy.sh <commit-sha>
```

Then verify from **outside** the host — the in-container checks cannot see a
broken nginx config or a firewall rule:

```bash
curl -fsS https://roamingwandering.com/api/v1/health/ready
curl -fsSI https://roamingwandering.com/ | grep -i strict-transport
curl -s -o /dev/null -w '%{http_code}\n' https://roamingwandering.com/api/v1/docs   # expect 403
```

Then <https://www.ssllabs.com/ssltest/> — aim for A+.

---

## Routine operations

### Deploying

```bash
./scripts/deploy.sh 1a2b3c4     # a SHA, never `latest`
./scripts/deploy.sh --rollback
```

The script pulls before stopping anything, runs migrations as their own step,
waits for **readiness** (not liveness), and rolls back automatically if the new
version never becomes ready.

> **`--rollback` reverts code, not schema.** If the deploy you are undoing
> included a migration, check that the old code can run against the new schema
> before rolling back. Additive migrations are safe; a dropped column is not.

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=200 api
```

For anything beyond a tail, use Grafana → Explore → Loki. Logs are structured
JSON and carry a `request_id` that also appears in the nginx access log, so one
guest complaint traces from the edge to the stack trace:

```logql
{service="api"} | json | request_id = "abc123"
{service="api", level="error"} |= "payment"
```

### Dashboards

Grafana is bound to `127.0.0.1` deliberately. Reach it over SSH:

```bash
ssh -L 3000:localhost:3000 deploy@host   # then http://localhost:3000
```

A Grafana on the public internet is your traffic, error rates and revenue
behind one password.

### Backups

Hourly, automatic. Each run dumps, **verifies by restoring into a scratch
database**, encrypts, uploads, then prunes — in that order, so a corrupt dump
is never stored and pruning never runs before a successful upload.

```bash
docker compose -f docker-compose.prod.yml exec backup restore --list
docker compose -f docker-compose.prod.yml exec backup restore --latest --into rehearsal
```

**Rehearse the restore monthly.** Put it in a calendar. An untested backup is a
reassuring file of unknown value, and the day you find out is the worst
possible day. The rehearsal restores into a scratch database and never touches
production.

Full recovery needs the age private key, which is deliberately not on the host:

```bash
docker compose -f docker-compose.prod.yml exec \
  -e AGE_IDENTITY_FILE=/tmp/age-key.txt backup \
  restore --latest --confirm-production-overwrite
```

---

## What is monitored, and what pages

Every alert in `monitoring/prometheus/rules/alerts.yml` answers yes to: *would
you want to be woken for this?* There is no "CPU above 80%" rule — high CPU is
not a problem, slow requests and failed bookings are, and those are measured
directly.

**Pages a human** (PagerDuty): API down, Postgres down, Redis down, error rate
above 2%, booking or payment errors above 0.5%, the outbox not draining, disk
under 5%, no verified backup in 26 hours.

**Slack, until morning**: worker down, p95 over 2s, connection pool over 80%,
replication lag, queue backlog, disk under 15%, certificate under 14 days.

Two of those deserve explanation:

- **`OutboxNotDraining`** pages because nothing breaks loudly when it stalls.
  Refunds requested by cancellations simply never reach the payment module, and
  the first symptom is a guest asking where their money is.
- **`BackupMissing`** pages for something that is not currently broken. It is
  the failure most likely to go unnoticed, because nothing else changes.

Alertmanager inhibits consequences: if Postgres is down you get one page, not
five.

---

## Environments

| | Production | Staging |
|---|---|---|
| Razorpay | **live keys** | **test keys** |
| AI | off by default | on — exercise prompt changes first |
| Backup retention | 30 days | 7 |
| Deploy approval | required reviewer | automatic |

Staging must match production in *structure* or it stops predicting anything,
and must not share its *credentials* or it is production with a different name.
The single most important line in `env/staging.env.example` is the Razorpay
test key: live keys on staging means a QA click charges a real card.

---

## Recovery

### The site is down

```bash
docker compose -f docker-compose.prod.yml ps        # what is not running
docker compose -f docker-compose.prod.yml logs --tail=200 api
df -h                                               # disk full is the usual cause
```

A full disk stops Postgres accepting writes and it does not always recover
cleanly. Usual culprits: Loki chunks, Docker images, an unrotated WAL.

### A bad deploy

```bash
./scripts/deploy.sh --rollback
```

### The database is corrupt or lost

1. Get the age private key from the password manager.
2. `restore --list`, choose a point before the damage.
3. `restore --key <key> --into rehearsal` and check the row counts first.
4. Only then `--confirm-production-overwrite`.

Step 3 is not optional. Restoring straight over production means discovering
the backup was from after the damage with nothing left to go back to.

### Certificates expired

Renewal has been failing for a fortnight if this happens — the alert fires at
14 days.

```bash
docker compose -f docker-compose.prod.yml logs certbot
docker compose -f docker-compose.prod.yml run --rm certbot renew --force-renewal
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Security notes

Decisions worth understanding before changing them.

- **Secrets are files, not environment variables.** The JWT keys mount at
  `/run/secrets`. An env var is visible in `docker inspect`, in a crash dump,
  and in the process list of anything that shells out.
- **HSTS is set with `preload`.** Preload is effectively irreversible — once
  it ships in a browser release, the domain and every subdomain are HTTPS-only
  for the lifetime of that install. Do not add a subdomain that cannot serve
  TLS.
- **The default server block returns 444.** Without it, a request with an
  unknown `Host` falls through to the first server block and serves the
  customer site to anyone scanning the IP.
- **`/metrics`, `/docs` and `/openapi.json` are blocked at the edge.** The docs
  describe every endpoint and schema; metrics expose request rates and error
  counts.
- **Backups go to a different bucket from media, ideally a different
  account.** A compromise that can write to media must not be able to delete
  backups. That is the shape of every ransomware incident.
- **Two Razorpay secrets, deliberately.** `key_secret` signs callbacks and
  authenticates API calls; `webhook_secret` signs webhooks. A leaked webhook
  secret must not let anyone call the API.

---

## Files

```
deploy/
├── docker-compose.prod.yml    the whole topology
├── .env                       secrets — gitignored, chmod 600
├── secrets/                   JWT keys — gitignored
├── env/
│   ├── production.env.example
│   └── staging.env.example
├── nginx/
│   ├── nginx.conf             TLS, rate zones, JSON logging
│   ├── conf.d/                per-host routing and CSP
│   └── snippets/              tls, security headers, proxy
├── certbot/init-letsencrypt.sh
├── monitoring/
│   ├── prometheus/            scrape config + alert rules
│   ├── alertmanager/          routing and inhibition
│   ├── grafana/provisioning/  datasources, dashboards
│   ├── loki/  promtail/       log aggregation
├── backup/
│   ├── backup.sh              dump → verify → encrypt → upload → prune
│   └── restore.sh             read this before you need it
└── scripts/
    ├── deploy.sh
    └── gen-jwt-keys.sh
```

---

## What this deployment promises, and what it does not

Written down because an availability target nobody has stated is an
availability target nobody can miss — and because the alternative to fixing the
single point of failure is *knowing* you have one.

### The failure domain is one machine

Postgres, Redis, the API, the workers, Prometheus and Grafana all run as
containers on a single host, with Postgres on a local volume. There is no
replica, no failover, and no second machine. Losing the host loses everything
running on it at once, including the monitoring that would tell you.

`DATABASE_REPLICA_DSN` is wired through the application and used for admin and
vendor reporting — but nothing is deployed to it, so it points at the primary.
The code is ready for a replica; the infrastructure has none.

### RPO — how much data a total loss costs

**Up to one hour**, and in the worst realistic case **up to 26 hours**.

Backups run hourly, so an ordinary host loss costs at most the writes since the
last successful dump. But `BackupStale` only fires after 26 hours without a
success, so a backup that starts failing at 09:00 is not paged until the
following morning. Everything written in between is gone if the host dies in
that window.

Narrowing this means alerting at, say, three missed backups rather than
twenty-six, and accepting the page. That is a deliberate trade and it has not
been made yet.

### RTO — how long recovery takes

**Unmeasured.** Recovery is: provision a host, install Docker, restore the
secrets from the password manager, `restore --latest`, bring the stack up.

An unmeasured RTO is not a number, it is a hope. Rehearse it — the drill is in
[Recovery](#recovery) — and replace this paragraph with the measured figure.
Until then, assume hours and plan accordingly.

### What would change these numbers

In rough order of value per unit of effort:

| Change | RPO | RTO |
|---|---|---|
| Alert on 3 missed backups instead of 26 | 1 h | unchanged |
| Managed Postgres with PITR | seconds | minutes |
| Warm standby host | unchanged | minutes |

Managed Postgres is the single highest-value change here: it collapses both
numbers at once and removes the failure mode that no amount of care on this
host protects against.

### What this deployment is appropriate for

A single host with hourly verified backups is a reasonable place to start, and
it is genuinely better than a lot of what runs in production. It is not
appropriate once an hour of lost bookings costs more than a managed database —
which for a platform taking real payments is quite soon.

## Known gaps

Stated rather than discovered:

- **No second host.** Recovery from host loss is provision-and-restore. Measure
  it during a rehearsal so the number is known.
- **No read replica by default.** `DATABASE_REPLICA_DSN` is wired through and
  the code uses it for admin and vendor reporting; unset, both point at the
  primary. Add one when reporting starts affecting checkout latency.
- **`ProbeSSLExpiry` needs blackbox-exporter.** The certificate alert rule is
  written but has no exporter configured to feed it. Add
  `prom/blackbox-exporter` and a probe job, or the rule never fires.
- **Grafana dashboards are provisioned but empty.** The datasources and folder
  are configured; the dashboard JSON is not written. Build them from the
  metrics the alert rules already use.
