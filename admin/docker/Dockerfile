# syntax=docker/dockerfile:1.9
#
# The admin panel. A build container and a static output — the runtime image serves
# files and runs no JavaScript.
#
# A separate image from the customer site, deliberately: none of this code
# belongs in the bundle a member of the public downloads. Merged, it would ship
# every internal route, permission name and API path to anyone who opens the
# home page.
#
# The decision that shapes this file: **Vite inlines `VITE_*` variables at
# build time**, not at runtime. There is no way to build one image and point it
# at staging or production afterwards, so the API base URL is a build argument
# and each environment gets its own image tag. Pretending otherwise — an
# entrypoint that rewrites the bundle on boot — is a common trick and a bad
# one: it defeats subresource integrity, breaks the content hash the CDN caches
# on, and fails silently when the placeholder string gets minified.
#
# The corollary is that **no secret may ever be a build argument here.** Every
# `VITE_*` value ends up in a file the browser downloads. There is nothing here
# staff could not read from the network tab anyway; there must never be
# anything else.

ARG NODE_VERSION=22

# ══════════════════════════════════════════════════════════════════════════
# Stage 1 — build
# ══════════════════════════════════════════════════════════════════════════
FROM node:${NODE_VERSION}-alpine AS builder

WORKDIR /build

# Dependency layer, cached until the lockfile changes. `npm ci` rather than
# `npm install`: it installs exactly the lockfile and fails if the two have
# drifted, which is the difference between a reproducible build and one that
# picks up a minor release on a Tuesday.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY . .

# Public configuration only. Repeated as ENV because Vite reads the
# environment, not the build args.
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_SENTRY_DSN=
ARG VITE_APP_VERSION=dev
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_SENTRY_DSN=${VITE_SENTRY_DSN} \
    VITE_APP_VERSION=${VITE_APP_VERSION}

# `tsc -b` before `vite build`: Vite transpiles without typechecking, so
# without this a type error ships.
RUN npm run build

# ══════════════════════════════════════════════════════════════════════════
# Stage 2 — runtime
# ══════════════════════════════════════════════════════════════════════════
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# The unprivileged image runs as UID 101 and listens on 8080 — a container that
# needs no root to bind its port is a container that needs no root at all.
USER 101

COPY --from=builder --chown=101:101 /build/dist /usr/share/nginx/html
COPY --chown=101:101 docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
