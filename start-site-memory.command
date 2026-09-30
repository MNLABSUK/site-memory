#!/bin/bash
# Site Memory one-click launcher (double-click in Finder). Survives closing Terminal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
LOG="$ROOT/site-memory.log"
PIDFILE="$ROOT/site-memory.pid"
PORT="${SITE_MEMORY_PORT:-43167}"
HOST="${SITE_MEMORY_HOST:-127.0.0.1}"   # set to 0.0.0.0 to use it from your phone on the same Wi-Fi

# First run: create the virtualenv and install dependencies.
if [[ ! -x .venv/bin/python ]]; then
  echo "First run: creating .venv and installing requirements…"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example (dry-run until you add NEBIUS_API_KEY)."
fi

# Already running? Just open it.
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  RUNNING_PORT="$(cat "$ROOT/.site-memory.port" 2>/dev/null || echo "$PORT")"
  if curl -fsS "http://127.0.0.1:$RUNNING_PORT/api/status" 2>/dev/null | grep -q '"Site Memory"'; then
    echo "Site Memory already running: http://127.0.0.1:$RUNNING_PORT/"
    [[ -z "${SITE_MEMORY_NO_OPEN:-}" ]] && open "http://127.0.0.1:$RUNNING_PORT/" 2>/dev/null || true
    exit 0
  fi
fi

# Find a free port (never 43151 / Trade Memory, never 43149 / Desk Gate).
while lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || [[ "$PORT" == "43151" || "$PORT" == "43149" ]]; do
  PORT=$((PORT + 1))
done
echo "$PORT" > "$ROOT/.site-memory.port"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
nohup "$ROOT/.venv/bin/python" -m uvicorn site_memory.app:app --host "$HOST" --port "$PORT" >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
disown || true

for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1 && break
  sleep 0.25
done
echo "Site Memory running (pid $(cat "$PIDFILE")) at http://127.0.0.1:$PORT/  (log: $LOG)"
echo "Phone on the same Wi-Fi? See README > 'Use it on your phone'."
[[ -z "${SITE_MEMORY_NO_OPEN:-}" ]] && open "http://127.0.0.1:$PORT/" 2>/dev/null || true
