#!/usr/bin/env bash
set -euo pipefail

version=${1:?usage: deploy.sh <git-sha-or-tag>}
repo_dir=${REPO_DIR:-/srv/revenue-growth-sim/repository}
app_dir=${APP_DIR:-/srv/revenue-growth-sim}
release_dir=$app_dir/releases/$version

test -d $repo_dir/.git
git -C $repo_dir fetch --tags --prune
git -C $repo_dir rev-parse --verify $version^{commit} >/dev/null
test ! -e $release_dir
git -C $repo_dir worktree add --detach $release_dir $version

cd $release_dir
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
ln -sfn $release_dir $app_dir/current.next
mv -Tf $app_dir/current.next $app_dir/current
sudo systemctl restart revenue-growth-sim
curl --fail --silent --show-error http://127.0.0.1:8008/readyz >/dev/null
DEPLOY_BASE_URL=${DEPLOY_BASE_URL:-http://127.0.0.1:5110} uv run python -m deploy.ops smoke
printf 'Deployed %s\n' $version
