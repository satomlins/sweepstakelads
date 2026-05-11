#!/usr/bin/env bash
# Runs on Oracle via SSH forced command. Called by GitHub Actions on push to main.
set -euo pipefail

APP_DIR=/home/opc/sweepstakelads

cd "$APP_DIR"
git fetch --quiet origin main
git reset --hard origin/main
/usr/local/bin/uv sync --frozen
sudo /usr/bin/systemctl restart sweepstakelads
sleep 2
curl -fsS http://127.0.0.1:8050/ > /dev/null
echo "Deploy OK"
