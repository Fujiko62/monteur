"""Recupere des images libres pour le b-roll, SANS cle par defaut (Openverse).

Usage:
  python fetch_media.py "intelligence artificielle" --n 3 --prefix ia
  python fetch_media.py "montage video" --provider pexels --n 3   (si PEXELS_API_KEY)

Telecharge dans remotion/public/media/ et imprime la liste JSON des fichiers crees
(a reutiliser comme "src" dans overlays.json, type image).
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from common import FFMPEG, ROOT, run, log

MEDIA = os.path.join(ROOT, "remotion", "public", "media")


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def openverse(query, n):
    q = urllib.parse.quote(query)
    url = (f"https://api.openverse.org/v1/images/?q={q}"
           f"&license_type=commercial&page_size={max(n*2,n)}&mature=false")
    data = json.loads(_get(url))
    out = []
    for r in data.get("results", []):
        u = r.get("url") or r.get("thumbnail")
        if u:
            out.append(u)
        if len(out) >= n:
            break
    return out


def pexels(query, n):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        log("PEXELS_API_KEY absent -> repli sur Openverse.")
        return openverse(query, n)
    q = urllib.parse.quote(query)
    url = f"https://api.pexels.com/v1/search?query={q}&per_page={n}&orientation=portrait"
    data = json.loads(_get(url, headers={"Authorization": key}))
    return [p["src"]["large2x"] for p in data.get("photos", [])][:n]


def normalize(raw, dst):
    """Ecrit les octets bruts puis reencode en jpg propre via ffmpeg."""
    tmp = dst + ".raw"
    open(tmp, "wb").write(raw)
    try:
        run([FFMPEG, "-y", "-i", tmp, "-frames:v", "1", "-q:v", "3", dst])
        ok = os.path.exists(dst) and os.path.getsize(dst) > 2000
    except SystemExit:
        ok = False
    if os.path.exists(tmp):
        os.remove(tmp)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--provider", default="openverse", choices=["openverse", "pexels"])
    ap.add_argument("--prefix", default=None)
    a = ap.parse_args()
    os.makedirs(MEDIA, exist_ok=True)
    prefix = a.prefix or re.sub(r"[^a-z0-9]+", "-", a.query.lower())[:24].strip("-")

    urls = pexels(a.query, a.n) if a.provider == "pexels" else openverse(a.query, a.n)
    if not urls:
        log(f"aucune image trouvee pour '{a.query}'.")
        print(json.dumps([]))
        return
    saved = []
    for i, u in enumerate(urls):
        name = f"{prefix}_{i}.jpg"
        dst = os.path.join(MEDIA, name)
        try:
            if normalize(_get(u), dst):
                saved.append(name)
                log(f"image: {name}")
        except Exception as e:
            log(f"echec {u[:60]}: {str(e)[:80]}")
    print(json.dumps(saved, ensure_ascii=False))


if __name__ == "__main__":
    main()
