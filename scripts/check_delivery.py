"""CONTROLE QUALITE FINAL d'une livraison — a lancer AVANT de declarer la video finie.
Verifie mecaniquement ce que l'oeil oublie : structure du dossier, durees, format,
niveaux audio, noirs en tete/queue, miniature conforme, shorts <= 20s.

Usage: python check_delivery.py livraisons/<nom>
Sortie: PASS/FAIL par regle + code retour 1 si au moins un FAIL (les WARN ne bloquent pas).
"""
import argparse
import glob
import os
import re
import subprocess
import sys
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, FFPROBE, log

FAILS = []
WARNS = []


def check(ok, label, warn=False):
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    print(f"  [{tag}] {label}")
    if not ok:
        (WARNS if warn else FAILS).append(label)


def probe(path, entries, stream=None):
    cmd = [FFPROBE, "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip()


def audio_stats(path, ss=None, t=None):
    cmd = [FFMPEG, "-v", "info"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"mean_volume: ([-\d.]+) dB", r.stderr or "")
    x = re.search(r"max_volume: ([-\d.]+) dB", r.stderr or "")
    return (float(m.group(1)) if m else None, float(x.group(1)) if x else None)


def black_at(path, ss, t):
    r = subprocess.run([FFMPEG, "-v", "info", "-ss", str(ss), "-i", path, "-t", str(t),
                        "-vf", "blackdetect=d=0.5:pix_th=0.06", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return "black_start" in (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery_dir")
    a = ap.parse_args()
    d = a.delivery_dir.rstrip("/\\")
    name = os.path.basename(d)
    print(f"=== CONTROLE QUALITE : {name} ===")

    # --- structure ---
    print("- Structure du dossier (regle livraison minimale)")
    check(re.fullmatch(r"[a-z0-9-]+", name) is not None,
          f"nom de dossier parlant en kebab-case ('{name}')")
    entries = sorted(os.listdir(d))
    allowed = {f"{name}.mp4", "miniature.png", "shorts"}
    extra = [e for e in entries if e not in allowed]
    check(not extra, f"AUCUN fichier en trop (trouve: {extra or 'rien'})")
    video = os.path.join(d, f"{name}.mp4")
    check(os.path.exists(video), f"video presente ({name}.mp4)")
    thumb = os.path.join(d, "miniature.png")
    check(os.path.exists(thumb), "miniature.png presente")
    if not os.path.exists(video):
        sys.exit(1)

    # --- video principale ---
    print("- Video principale")
    dur = float(probe(video, "format=duration") or 0)
    check(dur > 60, f"duree {dur/60:.1f} min (> 1 min)")
    wh = probe(video, "stream=width,height", "v:0").split("\n")[0]
    check(bool(wh), f"flux video lisible ({wh})")
    ach = probe(video, "stream=channels", "a:0")
    check(bool(ach), "flux audio present")
    mean, mx = audio_stats(video)
    if mean is not None:
        check(-20 <= mean <= -10, f"loudness moyenne {mean:.1f} dB (attendu ~-16)", warn=True)
        check(mx is not None and mx <= -0.1, f"pic audio {mx:.1f} dB (pas de clipping)")
    check(not black_at(video, 0, 2.0), "pas d'ecran noir au demarrage (2 premieres s)")
    check(not black_at(video, max(0, dur - 2.5), 2.5), "pas d'ecran noir en fin (2.5 dernieres s)")

    # --- miniature ---
    if os.path.exists(thumb):
        print("- Miniature")
        try:
            from PIL import Image
            im = Image.open(thumb)
            check(im.size == (1280, 720), f"taille {im.size[0]}x{im.size[1]} (attendu 1280x720)")
            check(os.path.getsize(thumb) < 2_000_000, "poids < 2 MB (limite YouTube)")
        except ImportError:
            check(True, "PIL absent : taille non verifiee", warn=True)

    # --- shorts ---
    sdir = os.path.join(d, "shorts")
    if os.path.isdir(sdir):
        print("- Shorts")
        shorts = sorted(glob.glob(os.path.join(sdir, "*.mp4")))
        check(bool(shorts), "le dossier shorts/ n'est pas vide (sinon le supprimer)")
        for s in shorts:
            sd = float(probe(s, "format=duration") or 0)
            base = os.path.basename(s)
            check(sd <= 20.5, f"{base}: {sd:.1f}s (regle <= 20s)")
            check(bool(re.fullmatch(r"short-[a-z0-9-]+\.mp4", base)),
                  f"{base}: nommage short-<sujet>.mp4")
            wh = probe(s, "stream=width,height", "v:0").split("\n")[0]
            check(wh.startswith("1080,1920"), f"{base}: vertical 1080x1920 ({wh})")
            # le hook doit etre a l'ecran DES la 1re seconde -> pas de noir en tete
            check(not black_at(s, 0, 1.0), f"{base}: pas de noir sur la 1re seconde (hook visible)")

    print()
    if FAILS:
        log(f"ECHEC : {len(FAILS)} probleme(s) bloquant(s). NE PAS livrer en l'etat.")
        sys.exit(1)
    log(f"QC OK ({len(WARNS)} avertissement(s)). Livraison conforme.")


if __name__ == "__main__":
    main()
