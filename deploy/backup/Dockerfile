# The backup sidecar.
#
# Postgres client tools, the AWS CLI and age, on a schedule. Deliberately not
# built on the application image: this container holds credentials that can
# read the whole database and write to the backup bucket, and it should share
# as little code with the internet-facing service as possible.

FROM postgres:17-alpine

RUN apk add --no-cache \
      aws-cli \
      age \
      bash \
      curl \
      coreutils \
      tzdata

COPY backup.sh  /usr/local/bin/backup
COPY restore.sh /usr/local/bin/restore
RUN chmod +x /usr/local/bin/backup /usr/local/bin/restore

# The textfile collector directory node-exporter reads. A volume in compose
# would be cleaner; a bind is what makes the metric visible across containers
# without giving node-exporter a database credential.
VOLUME /var/lib/backup

# Hourly, on the hour, with a jitter so it never coincides exactly with a
# deploy or a Celery beat sweep. Runs one immediately on boot so a fresh
# deployment is not an hour without a backup.
ENTRYPOINT ["/bin/bash", "-c", "\
  echo 'backup: starting, first run now, then hourly'; \
  backup || echo 'backup: initial run failed, will retry on the hour'; \
  while :; do \
    sleep $(( 3600 - $(date +%s) % 3600 + RANDOM % 120 )); \
    backup || echo 'backup: run failed'; \
  done"]
