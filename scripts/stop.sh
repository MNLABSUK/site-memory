#!/bin/bash
# Stop the Site Memory server started by start-site-memory.command
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/site-memory.pid" ]] && kill "$(cat "$ROOT/site-memory.pid")" 2>/dev/null; then
  echo "Stopped Site Memory."
else
  echo "Site Memory wasn't running."
fi
rm -f "$ROOT/site-memory.pid"
