# VM deployment runbook

The non-production VM exposes the application on port `5110`. Nginx serves
the React build and proxies `/api/` to Uvicorn on `127.0.0.1:8008`; port
`8008` is intentionally not public.

## One-time VM setup

Install Python 3.11, `uv`, Node 20, Nginx, Git and curl. Create the service
account and release directories, then clone the repository:

```bash
sudo useradd --system --home /srv/revenue-growth-sim --shell /usr/sbin/nologin revenue-growth
sudo install -d -o revenue-growth -g revenue-growth /srv/revenue-growth-sim/releases
sudo -u revenue-growth git clone <repository-url> /srv/revenue-growth-sim/repository
sudo cp deploy/vm/revenue-growth-sim.service /etc/systemd/system/
sudo cp deploy/vm/nginx-revenue-growth-sim.conf /etc/nginx/sites-available/revenue-growth-sim
sudo ln -s /etc/nginx/sites-available/revenue-growth-sim /etc/nginx/sites-enabled/revenue-growth-sim
sudo nginx -t && sudo systemctl daemon-reload && sudo systemctl reload nginx
```

Store `OPENAI_API_KEY` and other runtime settings in `/etc/revenue-growth-sim.env`
with mode `0600`; never place them in the release directory or Git history.

## Deploy and rollback

Run these from a checked-out release on the VM. `VERSION` must be an existing
Git SHA or tag. Deployment creates a detached worktree under
`/srv/revenue-growth-sim/releases/`, builds the UI, atomically updates the
`current` symlink, restarts systemd, and runs the smoke verifier.

```bash
make deploy VERSION=<git-sha-or-tag>
make rollback VERSION=<previous-git-sha-or-tag>
```

`make smoke` uses `DEPLOY_BASE_URL` (default `http://127.0.0.1:5110`) to
check liveness, readiness, a fixed supported-result hash, and a refusal.

## Health and failures

- `http://<vm-host>:5110/api/healthz` confirms the process is alive.
- `http://<vm-host>:5110/api/readyz` confirms data, support envelope and
  engine assets load correctly.
- LLM outages affect only the agent endpoint; scenario evaluation and UI
  remain available.
- If readiness fails after deployment, immediately run `make rollback` with
  the prior release version, then inspect `journalctl -u revenue-growth-sim`.
- A result-hash mismatch means the deployed engine/data no longer matches the
  known smoke baseline; rollback and investigate before serving users.
