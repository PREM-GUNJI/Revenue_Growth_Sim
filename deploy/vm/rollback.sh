#!/usr/bin/env bash
set -euo pipefail

version=${1:?usage: rollback.sh <previous-git-sha-or-tag>}
app_dir=${APP_DIR:-/srv/revenue-growth-sim}
release_dir=$app_dir/releases/$version

test -d $release_dir
ln -sfn $release_dir $app_dir/current.next
mv -Tf $app_dir/current.next $app_dir/current
sudo systemctl restart revenue-growth-sim
curl --fail --silent --show-error http://127.0.0.1:8008/readyz >/dev/null
DEPLOY_BASE_URL=${DEPLOY_BASE_URL:-http://127.0.0.1:5110} $release_dir/.venv/bin/python -m deploy.ops smoke
printf 'Rolled back to %s\n' $version
