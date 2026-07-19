"""LES YEUX A LA DEMANDE : extrait N frames autour d'un instant et fabrique une planche.

Usage:
  python scripts/peek.py "<video>" <t> [--n 3] [--span 3] [--out work/x/peek]
  python scripts/peek.py "<video>" 289 --n 3 --span 4

Sort une planche contact <out>/peek_<t>.jpg que Claude REGARDE (outil Read).
3 frames par defaut : pour ne pas juger sur une seule image vide et voir le contexte.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, run, log

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("t", type=float)
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--span", type=float, default=3.0, help="ecart total en secondes")
ap.add_argument("--out", default=None)
a = ap.parse_args()

out = a.out or os.path.join(os.path.dirname(__file__), "..", "work", "_peek")
os.makedirs(out, exist_ok=True)

times = [max(0.0, a.t - a.span / 2 + i * (a.span / max(1, a.n - 1))) for i in range(a.n)] if a.n > 1 else [a.t]
frames = []
for i, t in enumerate(times):
    f = os.path.join(out, f"f{i}.jpg")
    run([FFMPEG, "-v", "error", "-ss", str(t), "-i", a.video, "-frames:v", "1", "-q:v", "5",
         "-vf", "scale=520:-2,format=yuvj420p", "-strict", "unofficial", "-y", f])
    frames.append((t, f))

sheet = os.path.join(out, f"peek_{int(a.t)}.jpg")
if len(frames) > 1:
    ins = []
    for _, f in frames:
        ins += ["-i", f]
    run([FFMPEG, "-v", "error", *ins, "-filter_complex",
         "".join(f"[{i}]" for i in range(len(frames))) + f"hstack={len(frames)},format=yuvj420p",
         "-strict", "unofficial", "-y", sheet])
else:
    import shutil
    shutil.copy(frames[0][1], sheet)

log(f"frames a t={', '.join(f'{t:.1f}' for t, _ in frames)}")
print(sheet)
