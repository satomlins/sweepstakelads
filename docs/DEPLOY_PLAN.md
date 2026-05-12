# Deployment plan — sweepstakelads to Oracle Cloud

Target: `sweepstakelads.stomlins.com`, served by gunicorn on the Oracle box behind the existing cloudflared tunnel.

## Branch strategy

- `wc2026` is the deployment branch (has the 2026 code; `main` predates it).
- No code edits needed for deploy → no new branch required.
- CLAUDE.md update lands on `wc2026` (uncommitted; bundle with next commit).
- Unstaged `s1.css` change stays untouched; deploy uses whatever has been pushed to GitHub.

## Update workflow (steady state)

Always dev locally, push, then pull on Oracle:

```bash
# Local
git commit && git push origin wc2026

# Oracle
ssh stomlins-oracle
cd /home/opc/sweepstakelads
git pull
sudo systemctl restart sweepstakelads
```

If `pyproject.toml` changed, also run `uv sync` on Oracle before the restart.

No rsync, no manual venv work, no secrets pasted at deploy time.

## One-time Oracle setup

### 1. Push `wc2026` to GitHub

Verify the branch is on the remote before cloning on Oracle.

```bash
git remote -v                  # confirm GitHub URL
git push origin wc2026
```

### 2. SSH and clone

```bash
ssh -A stomlins-oracle         # -A forwards SSH agent so git clone over SSH works
git clone -b wc2026 git@github.com:<owner>/sweepstakelads.git /home/opc/sweepstakelads
cd /home/opc/sweepstakelads
uv sync
```

### 3. Env file (SELinux-safe location)

The app needs no secrets, but the systemd pattern requires an `EnvironmentFile` outside `/home/opc/`:

```bash
sudo touch /etc/sysconfig/sweepstakelads
sudo chmod 0600 /etc/sysconfig/sweepstakelads
sudo chown opc:opc /etc/sysconfig/sweepstakelads
sudo restorecon /etc/sysconfig/sweepstakelads
```

### 4. Systemd unit

Write `/etc/systemd/system/sweepstakelads.service`:

```ini
[Unit]
Description=Sweepstakelads Dash app
After=network.target

[Service]
User=opc
WorkingDirectory=/home/opc/sweepstakelads
EnvironmentFile=/etc/sysconfig/sweepstakelads
ExecStart=/usr/local/bin/uv run gunicorn app:server --bind 127.0.0.1:8050 --workers 1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Why one worker: Dash workers race on `assets/*.csv` writes during the 5-minute cache refresh; one process avoids the race.

Why `/usr/local/bin/uv`: SELinux's `init_t` cannot traverse `/home/opc/`, so `ExecStart` must point at a binary outside it (`/usr/local/bin/uv` has `bin_t`). `uv` then runs as `opc` and reaches the venv freely.

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sweepstakelads
systemctl status sweepstakelads
curl -sI http://127.0.0.1:8050/   # expect HTTP 200
```

### 5. Cloudflared ingress

Edit the existing tunnel config (already serving other apps on this box) to add a rule for the new hostname above the catch-all 404:

```yaml
ingress:
  - hostname: sweepstakelads.stomlins.com
    service: http://localhost:8050
  # ...existing rules...
  - service: http_status:404
```

Route DNS and restart:

```bash
sudo cloudflared tunnel route dns <tunnel-name> sweepstakelads.stomlins.com
sudo systemctl restart cloudflared
```

### 6. Verify

```bash
curl -sI https://sweepstakelads.stomlins.com/   # expect HTTP 200
```

Open the URL in a browser and confirm the dashboard renders with the pre-draw "TBC" state.

## Hard constraints (from `~/projects/stomlins-oracle`)

- **Billing must stay $0** — always-free tier only on Oracle.
- **No `setenforce 0`** — work with SELinux, not around it.
- **Bind to `127.0.0.1`**, never `0.0.0.0` — cloudflared handles public exposure.
- **No rsync of code or secrets** — clone from GitHub, paste secrets manually into `/etc/sysconfig/<app>` if ever needed.
- **`ExecStart` must not point into `/home/opc/.venv/`** — use `/usr/local/bin/uv run ...`.
- **`EnvironmentFile` must not live under `/home/opc/`** — use `/etc/sysconfig/<app>`.

## Auto-deploy setup (Phase 4)

Push to `main` triggers `.github/workflows/deploy.yml`: tests run, then on success SSH into Oracle and run `scripts/deploy.sh` via a forced command. The deploy script pulls the latest `main`, runs `uv sync --frozen`, restarts the service, and smoke-tests it locally.

### One-time local setup

```bash
# Generate a dedicated deploy key (no passphrase — it's locked down by forced command)
ssh-keygen -t ed25519 -f ~/.ssh/sweepstakelads_deploy -N ""
```

### One-time Oracle setup

SSH in manually the first time:

```bash
ssh stomlins-oracle
```

**1. Add deploy key with forced command** — append to `/home/opc/.ssh/authorized_keys`:

```
command="/home/opc/sweepstakelads/scripts/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 <paste public key here>
```

The `command=` restriction means even if the private key leaks, it can only trigger the deploy script — nothing else.

**2. Passwordless service restart** (for the deploy script):

```bash
echo 'opc ALL=(root) NOPASSWD: /usr/bin/systemctl restart sweepstakelads' \
  | sudo tee /etc/sudoers.d/sweepstakelads
sudo chmod 0440 /etc/sudoers.d/sweepstakelads
```

**3. Verify the forced command works** from your local machine:

```bash
ssh -i ~/.ssh/sweepstakelads_deploy opc@<oracle-host>
# Should run deploy.sh and print "Deploy OK", not open a shell
```

### GitHub secrets to add

In the repository settings → Secrets → Actions:

| Secret name | Value |
|---|---|
| `ORACLE_DEPLOY_KEY` | Contents of `~/.ssh/sweepstakelads_deploy` (the private key) |
| `ORACLE_HOST` | The Oracle instance **public** IP (currently `79.72.78.54`) — not the Tailscale IP, since GitHub Actions runners can't reach the Tailscale network |

**Security note:** SSH (port 22) must be open to the public internet on Oracle's VCN Security List. This is acceptable because: the forced command means even a leaked key can only trigger `deploy.sh`; ed25519 key-only auth (no password); and the deploy script is idempotent. Risk is bot scan noise in journalctl, not real compromise.

## Rollback

If a deploy breaks production:

```bash
ssh stomlins-oracle
cd /home/opc/sweepstakelads
git log --oneline -5          # find the previous good SHA
git reset --hard <sha>
sudo systemctl restart sweepstakelads
```

Then push a revert commit to `main` to keep git state consistent with the server.

## Confirmed values (resolved at deploy time 2026-05-10)

- GitHub remote: `https://github.com/satomlins/sweepstakelads.git`
- Cloudflared tunnel UUID: `dcd0bf6e-e2f4-4e36-9c2a-3f7d1b2566d7` (use UUID not name with `sudo /usr/local/bin/cloudflared` — `cloudflared` is not on sudo's PATH)
- `uv` for systemd: `/usr/local/bin/uv` (already installed; `/home/opc/.local/bin/uv` is the user install but SELinux blocks it from `init_t`)
