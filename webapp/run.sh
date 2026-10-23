#!/usr/bin/env sh
# The prosumer site on Linux or macOS: as run.cmd (makes .venv, installs, builds the page, serves on :8080).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
if [ ! -f .venv/installed.txt ]; then  # a failed install is tried again next time
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -e "..[lightgbm,net,fronius]" -r requirements.txt
  date > .venv/installed.txt
fi
if command -v npm >/dev/null 2>&1; then
  cd web
  [ -d node_modules ] || npm install
  npm run build
  cd ..
elif [ ! -f web/dist/index.html ]; then
  echo "npm not found and the page is not built: install Node.js 20+ and run again." >&2
  exit 1
fi
exec .venv/bin/python -m server.launch  # first free port from 8080, opens the browser; Ctrl+C stops it
