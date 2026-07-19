"""Extrait des frames du rendu pour que Claude REGARDE le resultat (les yeux locaux).

Usage: python review.py <video> [--frames 9] [--out <dir>] [--targets work/<nom>]
Sortie: <dir>/frame_XX.jpg + <dir>/contact_sheet.jpg
--targets : extrait EN PLUS une frame au MILIEU de chaque overlay/zoom du montage
(frame_overlay_<type>_<t>.jpg) — c'est la que la REGLE DES YEUX se joue, pas sur des
instants uniformes qui ratent 9 fois sur 10 un placement de 2-3s.
"""
import argparse
import os
from common import FFMPEG, run, log, load_json, ffprobe_info


def target_moments(work_dir, dur):
    """(t, label) au milieu de chaque overlay + zoom (timeline COUPEE : props.json)."""
    props_path = os.path.join(work_dir, "props.json")
    if not os.path.exists(props_path):
        return []
    props = load_json(props_path)
    out = []
    for o in props.get("overlays", []):
        t = (o.get("start", 0)) + (o.get("dur", 2)) / 2
        if 0 <= t < dur:
            out.append((t, f"overlay_{o.get('type', 'x')}"))
    for z in props.get("zooms", []):
        t = (z.get("start", 0) + z.get("end", 0)) / 2
        if 0 <= t < dur:
            out.append((t, "zoom"))
    return sorted(out)[:40]  # borne de securite sur les tres longs montages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--frames", type=int, default=9)
    ap.add_argument("--out", default=None)
    ap.add_argument("--targets", default=None,
                    help="dossier work : extrait aussi une frame par overlay/zoom")
    a = ap.parse_args()
    info = ffprobe_info(a.video)
    dur = info["duration"] or 1.0
    out = a.out or os.path.join(os.path.dirname(a.video), "review")
    os.makedirs(out, exist_ok=True)

    n = a.frames
    for i in range(n):
        t = dur * (i + 1) / (n + 1)
        dst = os.path.join(out, f"frame_{i:02d}.jpg")
        run([FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1",
             "-q:v", "3", dst])

    if a.targets:
        moments = target_moments(a.targets, dur)
        for t, label in moments:
            dst = os.path.join(out, f"frame_{label}_{t:07.2f}s.jpg")
            run([FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1",
                 "-q:v", "3", dst])
        if moments:
            log(f"review: +{len(moments)} frames ciblees sur les placements (REGLE DES YEUX).")
    # contact sheet (grille)
    cols = 3
    rows = (n + cols - 1) // cols
    sheet = os.path.join(out, "contact_sheet.jpg")
    fps_sel = n / dur
    run([FFMPEG, "-y", "-i", a.video,
         "-vf", f"fps={fps_sel:.5f},scale=480:-1,tile={cols}x{rows}",
         "-frames:v", "1", "-q:v", "3", sheet])
    log(f"review: {n} frames + contact_sheet.jpg dans {out}")
    log(f"contact_sheet: {sheet}")


if __name__ == "__main__":
    main()
