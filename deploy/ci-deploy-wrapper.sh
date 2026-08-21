#!/usr/bin/env bash
#
# Forced command for the CI deploy key (see authorized_keys entry on the VPS).
# Installed to /usr/local/bin/biofusion-deploy — deliberately OUTSIDE the repo
# worktree so a push cannot rewrite the command the CI key is allowed to run.
#
# The CI key can therefore only trigger a deploy of origin/main; any other
# command sent over that key is ignored.
set -euo pipefail

APP_DIR=/var/www/biofusion

cd "$APP_DIR"
git fetch --all --quiet
git reset --hard origin/main --quiet

exec bash "$APP_DIR/deploy.sh"
