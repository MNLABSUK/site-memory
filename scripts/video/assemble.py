"""Turn screencast frames + timeline into an MP4 with narration.

python3 assemble.py <recDir> <out.mp4> [audioDir] [fontPath]
audioDir holds s0.m4a..s7.m4a (optional). Waits on Nemotron 3 Super longer
than 6 s are sped up and labelled as such on screen.
"""
import json, os, subprocess, sys

rec, out = sys.argv[1], sys.argv[2]
audio_dir = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
font = sys.argv[4] if len(sys.argv) > 4 else None
tl = json.load(open(os.path.join(rec, "timeline.json")))
t0 = tl["t0"]; frames = tl["frames"]; events = {e["name"]: e["t"] for e in tl["events"]}
KEEP = 6.0  # waits longer than this are sped up (and labelled if ffmpeg has drawtext)
fast = [(f["a"], f["b"]) for f in tl["fast"] if f.get("a") and f.get("b") and f["b"] - f["a"] > KEEP]

def out_t(t):
    o = t - t0
    for a, b in fast:
        if t <= a: continue
        span = b - a; seen = min(t, b) - a
        o -= seen - seen * (KEEP / span)
    return o

end = events["end"]
frames = [f for f in frames if f["ts"] <= end]
lines = []
for i, f in enumerate(frames):
    nxt = frames[i + 1]["ts"] if i + 1 < len(frames) else end
    d = max(0.0, out_t(nxt) - out_t(max(f["ts"], t0)))
    if d <= 0: continue
    lines.append(f"file 'frames/f{f['n']:06d}.jpg'\nduration {d:.4f}")
lines.append(f"file 'frames/f{frames[-1]['n']:06d}.jpg'")
open(os.path.join(rec, "concat.txt"), "w").write("\n".join(lines) + "\n")
total = out_t(end)

vf = "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p"
has_drawtext = "drawtext" in subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
if font and fast and has_drawtext:
    parts = []
    for a, b in fast:
        s, e = out_t(a), out_t(b); x = (b - a) / KEEP
        txt = f"Nemotron 3 Super thinking · {b - a:.0f} s · shown {x:.0f}x faster"
        parts.append(f"drawtext=fontfile='{font}':text='{txt}':x=w-tw-40:y=34:fontsize=30:fontcolor=white:box=1:boxcolor=0x0b0e12@0.85:boxborderw=14:enable='between(t,{s:.2f},{e + 0.4:.2f})'")
    vf = ",".join([vf] + parts)

cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(rec, "concat.txt")]
filt = [f"[0:v]{vf}[v]"]; maps = ["-map", "[v]"]
if audio_dir:
    labels = []
    k = 1
    for n in range(8):
        p = os.path.join(audio_dir, f"s{n}.m4a")
        st = events.get(f"s{n}:start")
        if not os.path.exists(p) or st is None: continue
        delay = int((out_t(st) + (0.4 if n else 0.6)) * 1000)
        cmd += ["-i", p]; filt.append(f"[{k}:a]adelay={delay}|{delay}[a{k}]"); labels.append(f"[a{k}]"); k += 1
    if labels:
        filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad[a]"); maps += ["-map", "[a]"]
cmd += ["-filter_complex", ";".join(filt)] + maps + ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(json.dumps({"out": out, "seconds": round(total, 1), "fast": [(round(b - a, 1)) for a, b in fast],
                  "scene_starts": {k: round(out_t(v), 1) for k, v in events.items() if k.endswith(":start")}}))
