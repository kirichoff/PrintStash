#!/bin/sh
# Container entrypoint: bring the database to the latest schema, then exec the
# image command (CMD: uvicorn).
#
# Running migrations here — inside the image, on every start — means they happen
# however the container is launched (Compose, Portainer, Unraid, bare `docker
# run`), so a missing/edited `command:` can no longer skip them (issue #29).
# `app.db.migrate` is idempotent (a no-op at head) and self-heals an un-stamped
# "orphan" database. `set -e` aborts startup if a migration fails — before the
# app serves a single request, which is exactly when you want to find out.
set -e

uv run python -m app.db.migrate

exec "$@"
