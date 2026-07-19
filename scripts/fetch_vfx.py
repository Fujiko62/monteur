"""EFFETS VIDEO STOCK a la demande (Mixkit, libre usage commercial, sans attribution) :
pluie reelle, fumee, feu, confettis, light leaks, bokeh, poussiere, eclairs, neige...
La plus grande bibliotheque libre accessible sans cle — cherche, telecharge, prêt a
composer par blend mode dans le montage.

Usage:
  python fetch_vfx.py "rain window" --name pluie [--dur 8] [--n 1]
  -> remotion/public/media/pluie.mp4  puis dans overlays.json :
  {"type":"vfx","src":"pluie.mp4","blend":"screen","opacity":0.6,"start":120,"dur":6}
  (blend: screen=fond noir invisible | overlay | lighten | multiply... opacity 0..1 —
   TOUT est parametrable au niveau de l'overlay.)
Requetes utiles : rain window, smoke black background, fire black background, confetti,
light leak, bokeh lights, snow falling, dust particles, lightning storm, sparks.
"""
import argparse
import os
import re
import urllib.request
import urllib.parse
from common import FFMPEG, ROOT, run, log, die

MEDIA = os.path.join(ROOT, "remotion", "public", "media")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def search(query, n=4):
    q = urllib.parse.quote_plus(query)
    req = urllib.request.Request(f"https://mixkit.co/free-stock-video/search/?q={q}", headers=UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    # groupe par id, prefere 1080 puis 720
    ids = []
    for m in re.finditer(r"https://assets\.mixkit\.co/videos/(\d+)/\1-(1080|720)\.mp4", html):
        vid, res = m.group(1), m.group(2)
        entry = next((e for e in ids if e[0] == vid), None)
        if entry:
            if int(res) > int(entry[1]):
                ids[ids.index(entry)] = (vid, res)
        else:
            ids.append((vid, res))
        if len(ids) >= n:
            break
    return [f"https://assets.mixkit.co/videos/{v}/{v}-{r}.mp4" for v, r in ids]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--name", required=True)
    ap.add_argument("--dur", type=float, default=10, help="duree max gardee (boucle cote overlay)")
    ap.add_argument("--n", type=int, default=1, help="nombre de variantes (name, name2, ...)")
    a = ap.parse_args()
    os.makedirs(MEDIA, exist_ok=True)
    urls = search(a.query, max(4, a.n * 2))
    if not urls:
        die(f"aucun effet video trouve pour '{a.query}'.")
    log(f"{len(urls)} candidats pour '{a.query}'.")
    saved = 0
    for u in urls:
        if saved >= a.n:
            break
        name = a.name if saved == 0 else f"{a.name}{saved + 1}"
        tmp = os.path.join(MEDIA, f"_{name}.dl.mp4")
        out = os.path.join(MEDIA, f"{name}.mp4")
        try:
            req = urllib.request.Request(u, headers=UA)
            data = urllib.request.urlopen(req, timeout=90).read()
            if len(data) < 100000:
                raise ValueError("fichier trop petit")
            open(tmp, "wb").write(data)
            # normalise : coupe a --dur, reencode leger, sans audio
            run([FFMPEG, "-y", "-i", tmp, "-t", f"{a.dur:.2f}", "-an",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                 "-pix_fmt", "yuv420p", out])
            os.remove(tmp)
            log(f"vfx: {name}.mp4 ({len(data) // (1024*1024)} Mo, {u.rsplit('/',1)[-1]})")
            print(f"{name}.mp4")
            saved += 1
        except Exception as e:
            log(f"echec {u[:60]}: {str(e)[:80]}")
            if os.path.exists(tmp):
                os.remove(tmp)
    if not saved:
        die("aucun telechargement reussi.")


if __name__ == "__main__":
    main()
