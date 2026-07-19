"""Ajoute une musique de fond a une video DEJA rendue (ducking auto : la musique baisse
quand la voix parle). Rapide : la video est copiee, seul l'audio est re-encode.

Usage:
  python add_music.py <video_in> <music.mp3> [--out <video_out>] [--gain -20] [--no-duck]
Si <music.mp3> est un chemin relatif type "music/upbeat.mp3", il est cherche dans
remotion/public/. Peut aussi etre un mood (upbeat/chill/...) -> telecharge a la demande.
"""
import argparse
import math
import os
from common import FFMPEG, ROOT, run, log, die, ffprobe_info


def music_duration(path):
    import json as _json
    import subprocess as _sp
    from common import FFPROBE
    r = _sp.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def resolve_music(m):
    if os.path.exists(m):
        return m
    cand = os.path.join(ROOT, "remotion", "public", m)
    if os.path.exists(cand):
        return cand
    cand2 = os.path.join(ROOT, "remotion", "public", "music", m if m.endswith(".mp3") else m + ".mp3")
    if os.path.exists(cand2):
        return cand2
    # dernier recours : traiter m comme une ambiance et telecharger
    import subprocess, sys
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fetch_music.py"), m],
                       capture_output=True, text=True)
    rel = (r.stdout.strip().splitlines() or [""])[-1]
    p = os.path.join(ROOT, "remotion", "public", rel)
    if rel and os.path.exists(p):
        return p
    die(f"musique introuvable: {m}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_in")
    ap.add_argument("music")
    ap.add_argument("--out", default=None)
    ap.add_argument("--gain", type=float, default=-20.0, help="gain musique en dB")
    ap.add_argument("--no-duck", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.video_in):
        die(f"video introuvable: {a.video_in}")
    music = resolve_music(a.music)
    out = a.out or (os.path.splitext(a.video_in)[0] + "_music.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    # Boucle SANS couture : un -stream_loop brut redemarre le morceau sec (fin de morceau
    # -> attaque pleine), audible dans les moments calmes. On enchaine N copies du morceau
    # avec un fondu-enchaine de 2s entre chaque -> lit de musique continu.
    vdur = ffprobe_info(a.video_in)["duration"]
    mdur = music_duration(music)
    xf = 2.0
    n = max(1, math.ceil((vdur + 5) / max(1.0, mdur - xf))) if mdur > xf else 1
    inputs = ["-i", a.video_in] + ["-i", music] * n
    if n == 1:
        bed, chain = "[1:a]", ""
    else:
        cur, chain = "[1:a]", ""
        for i in range(2, n + 1):
            lab = f"[mx{i}]"
            chain += f"{cur}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{lab};"
            cur = lab
        bed = cur

    # loudnorm final : niveau YouTube (-16 LUFS) + plafond -1.5 dB. Sans lui, la somme
    # voix+musique CLIPPE a 0 dB (attrape par check_delivery sur une vraie livraison).
    master = "loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    if a.no_duck:
        fc = (f"{chain}{bed}volume={a.gain}dB[m];"
              f"[0:a][m]amix=inputs=2:duration=first:normalize=0,{master}")
    else:
        # ducking : la voix (sidechain) compresse la musique
        fc = (f"{chain}{bed}volume={a.gain}dB[mraw];"
              f"[0:a]asplit=2[a0][sc];"
              f"[mraw][sc]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=250[mduck];"
              f"[a0][mduck]amix=inputs=2:duration=first:normalize=0,{master}")

    log(f"mix musique ({os.path.basename(music)}, {a.gain}dB, "
        f"{'sans' if a.no_duck else 'avec'} ducking, {n} boucle(s) fondues)...")
    run([FFMPEG, "-y"] + inputs +
        ["-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", out])
    log(f"OK: {out}")


if __name__ == "__main__":
    main()
