"""TOUT EN TEXTE : dump la transcription mot-a-mot timecodee ("00:00.8 alors 00:01.3").

Usage:
  python scripts/dump_words.py work/<nom> [--from 120] [--to 300] [--sentences]

--sentences : regroupe par phrases (frontieres . ! ? ... ou pause > 2.5s), une par ligne.
C'est la matiere premiere du chef monteur : il LIT tout, puis donne des ordres precis.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import load_json  # noqa: F401  (force UTF-8 console via common)

ap = argparse.ArgumentParser()
ap.add_argument("work_dir")
ap.add_argument("--from", dest="t0", type=float, default=0.0)
ap.add_argument("--to", dest="t1", type=float, default=1e9)
ap.add_argument("--sentences", action="store_true")
a = ap.parse_args()

w = json.load(open(os.path.join(a.work_dir, "words.json"), encoding="utf-8"))["words"]
w = [x for x in w if a.t0 <= x["start"] <= a.t1]

def ts(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"

if a.sentences:
    cur, t0, last = [], None, 0.0
    def flush(end):
        global cur, t0
        if cur:
            print(f"{ts(t0)} -> {ts(end)} | {' '.join(cur)}")
        cur, t0 = [], None
    for x in w:
        if t0 is None:
            t0 = x["start"]
        if x["start"] - last > 2.5 and cur:
            flush(last)
            t0 = x["start"]
        cur.append(x["w"])
        last = x["end"]
        if x["w"].endswith((".", "!", "?", "…")) and len(cur) > 2:
            flush(x["end"])
    flush(last)
else:
    for x in w:
        print(f"{ts(x['start'])} {x['w']} {ts(x['end'])}")
