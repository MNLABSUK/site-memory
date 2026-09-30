#!/bin/bash
# Records the demo video from the real app (live Nemotron if .env has a key). macOS: uses `say` for the voiceover.
# Usage: scripts/video/make-video.sh [out.mp4]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; HERE="$ROOT/scripts/video"
OUT="${1:-$ROOT/video/site-memory-demo.mp4}"; WORK="$(mktemp -d /tmp/sm-video-XXXX)"; PORT=43177
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
mkdir -p "$(dirname "$OUT")" "$WORK/audio"
# 1. voiceover clips + durations
python3 - "$HERE/script.json" "$WORK/audio" <<'PY'
import json, subprocess, sys
script, out = json.load(open(sys.argv[1])), sys.argv[2]; durs = {}
for k, text in script.items():
    subprocess.run(["say", "-v", "Daniel", "-r", "182", "-o", f"{out}/{k}.aiff", text], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{out}/{k}.aiff", "-af", "loudnorm=I=-16:TP=-1.5", "-c:a", "aac", "-b:a", "160k", f"{out}/{k}.m4a"], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{out}/{k}.m4a"], capture_output=True, text=True).stdout
    durs[k] = float(d)
json.dump(durs, open(f"{out}/narr.json", "w")); print("narration:", {k: round(v, 1) for k, v in durs.items()}, "total", round(sum(durs.values()), 1))
PY
# 2. a fresh seeded instance (MN Labs demo data only) on its own port
SITE_MEMORY_DATA_DIR="$WORK/data" PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m uvicorn site_memory.app:app --host 127.0.0.1 --port $PORT >"$WORK/server.log" 2>&1 &
SERVER=$!; trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1 && break; sleep 0.25; done
curl -fsS "http://127.0.0.1:$PORT/api/status" | python3 -c "import json,sys; s=json.load(sys.stdin); print('mode:', s['mode'], s['model'], s['nightly_model'])"
# 3. record + assemble
node "$HERE/record.mjs" "$CHROME" "http://127.0.0.1:$PORT" "$WORK/rec" "$WORK/audio/narr.json"
FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"; [[ -f "$FONT" ]] && cp "$FONT" "$WORK/font.ttf"
python3 "$HERE/assemble.py" "$WORK/rec" "$OUT" "$WORK/audio" "$WORK/font.ttf"
echo "work dir: $WORK"
