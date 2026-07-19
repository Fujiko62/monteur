"""PRENDRE UN EXTRAIT : decoupe un clip de la source pour l'incruster (overlay "clip").

Usage:
  python scripts/grab_clip.py "<video>" <start> <end> --name replay1 [--mute]

Sort media/<name>.mp4 (720p, leger). L'utiliser ensuite dans overlays.json :
  {"type":"clip","src":"replay1.mp4","start":<t>,"dur":<d>,
   "params":{"x":0.72,"y":0.28,"w":0.42,"label":"LE REPLAY","border":"#FFE500","muted":true}}
x,y = centre (fractions ecran), w = largeur (fraction). Grand format : w 0.8+.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, ROOT, run, log

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("start", type=float)
ap.add_argument("end", type=float)
ap.add_argument("--name", required=True)
ap.add_argument("--mute", action="store_true")
ap.add_argument("--speed", type=float, default=1.0,
                help="ex: 0.5 = replay au ralenti x2 ; 2.0 = accelere x2")
a = ap.parse_args()

media = os.path.join(ROOT, "remotion", "public", "media")
os.makedirs(media, exist_ok=True)
out = os.path.join(media, f"{a.name}.mp4")
vf = "scale=-2:720" if a.speed == 1.0 else f"setpts=PTS/{a.speed:.4f},scale=-2:720"
cmd = [FFMPEG, "-v", "error", "-ss", str(a.start), "-t", str(a.end - a.start), "-i", a.video,
       "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
       "-pix_fmt", "yuv420p"]
if a.mute or a.speed != 1.0:
    cmd += ["-an"]  # un replay ralenti est muet (le son etire est laid)
else:
    cmd += ["-c:a", "aac", "-b:a", "128k"]
run(cmd + ["-y", out])
log(f"clip {a.end - a.start:.1f}s -> media/{a.name}.mp4")
print(out)
