"""MINIATURE YouTube (1280x720) sans outil externe : frame de la video + titre compose
par Remotion. Workflow chef monteur :
 1) --candidates : extrait des frames aux moments cles (brief.json si present) + planche
    contact -> REGARDE-les (Read) et choisis la plus expressive.
 2) --frame <t> --title "MON *TITRE*" : compose la miniature (mots en *etoiles* = couleur
    accent). Ameliore l'image (contraste/saturation/nettete) avant composition.
 3) Fais JUGER la miniature par Gemini : gemini_review.py --thumb <png>.

Usage:
  python make_thumbnail.py <work_dir> --candidates
  python make_thumbnail.py <work_dir> --frame 447.5 --title "J'AI *GAGNE* AVEC CA" \
      [--emoji 🏆] [--badge "EPISODE 1"] [--accent "#FFE500"] [--zoom 1.15] [--circle 0.7,0.4,0.1]
  python make_thumbnail.py <work_dir> --image chemin.jpg --title "..."   # image fournie
Sortie : <dossier de la video>/<nom>_miniature.png (ou --out).
"""
import argparse
import json
import os
import subprocess
import sys
from common import FFMPEG, ROOT, run, log, die, save_json, load_json, load_config, project_dir, safe_name

REMOTION = os.path.join(ROOT, "remotion")
MEDIA = os.path.join(REMOTION, "public", "media")


def extract_frame(video, t, dst, enhance=True):
    vf = "scale=1280:-2"
    if enhance:
        # leger boost punch miniature : contraste, saturation, nettete
        vf += ",eq=contrast=1.12:saturation=1.25:brightness=0.02,unsharp=5:5:0.8"
    run([FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
         "-vf", vf, "-q:v", "2", dst])


def candidates(work_dir, video):
    """Extrait des frames candidates aux moments cles + planche contact."""
    out_dir = os.path.join(work_dir, "thumb_candidates")
    os.makedirs(out_dir, exist_ok=True)
    times = []
    brief_p = os.path.join(work_dir, "brief.json")
    if os.path.exists(brief_p):
        brief = load_json(brief_p)
        for m in brief.get("moments_cles", []):
            if m.get("type") in ("hype", "fail", "punchline", "moment_visuel"):
                times.append(float(m.get("t", 0)))
    if not times:
        info = load_json(os.path.join(work_dir, "words.json"))
        dur = info.get("duration", 60)
        times = [dur * (i + 1) / 10 for i in range(9)]
    times = sorted(set(round(t, 1) for t in times))[:12]
    files = []
    for i, t in enumerate(times):
        dst = os.path.join(out_dir, f"cand_{i:02d}_t{int(t)}s.jpg")
        extract_frame(video, t, dst, enhance=False)
        files.append(dst)
    # planche contact
    sheet = os.path.join(out_dir, "contact_sheet.jpg")
    inputs = []
    for f in files:
        inputs += ["-i", f]
    n = len(files)
    cols = 3
    run([FFMPEG, "-y"] + inputs +
        ["-filter_complex",
         "".join(f"[{i}:v]scale=426:240[v{i}];" for i in range(n)) +
         "".join(f"[v{i}]" for i in range(n)) +
         f"xstack=inputs={n}:layout=" +
         "|".join(f"{(i % cols) * 426}_{(i // cols) * 240}" for i in range(n)),
         "-frames:v", "1", "-q:v", "3", sheet])
    log(f"{n} candidates -> {out_dir}")
    for i, (t, f) in enumerate(zip(times, files)):
        log(f"  [{i}] t={t}s  {os.path.basename(f)}")
    log(f"planche: {sheet}")
    print(sheet)


def compose(work_dir, video, args):
    bg = os.path.join(MEDIA, "thumb_bg.jpg")
    os.makedirs(MEDIA, exist_ok=True)
    if args.image:
        run([FFMPEG, "-y", "-i", args.image, "-vf",
             "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
             "eq=contrast=1.12:saturation=1.25,unsharp=5:5:0.8", "-q:v", "2", bg])
    elif args.frame is not None:
        extract_frame(video, args.frame, bg, enhance=True)
    else:
        die("donne --frame <t> ou --image <chemin> (ou lance --candidates d'abord).")

    props = {"image": "thumb_bg.jpg", "title": args.title, "accent": args.accent,
             "zoom": args.zoom, "offsetX": args.offset_x, "offsetY": args.offset_y,
             "darken": args.darken}
    if args.emoji:
        props["emoji"] = args.emoji
    if args.badge:
        props["badge"] = args.badge
    if args.circle:
        x, y, r = (float(v) for v in args.circle.split(","))
        props["circle"] = {"x": x, "y": y, "r": r}
    pfile = os.path.join(work_dir, "thumb_props.json")
    save_json(pfile, props)

    # abspath obligatoire : remotion still tourne avec cwd=REMOTION, un --out relatif
    # partirait dans remotion/ au lieu du dossier voulu.
    out = os.path.abspath(args.out) if args.out else os.path.join(project_dir(video), "miniature.png")
    npx = "npx.cmd" if os.name == "nt" else "npx"
    r = subprocess.run([npx, "remotion", "still", "src/index.ts", "Thumb", out,
                        f"--props={os.path.abspath(pfile)}"], cwd=REMOTION)
    if r.returncode != 0:
        die("rendu miniature echoue.")
    log(f"MINIATURE PRETE: {out}")
    print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--candidates", action="store_true")
    ap.add_argument("--frame", type=float)
    ap.add_argument("--image")
    ap.add_argument("--title", default="")
    ap.add_argument("--accent", default=None,
                    help="couleur des *mots* accent (defaut: config.da.accent — ta patte)")
    ap.add_argument("--emoji")
    ap.add_argument("--badge")
    ap.add_argument("--circle", help="x,y,r normalises 0..1")
    ap.add_argument("--zoom", type=float, default=1.08)
    ap.add_argument("--offset-x", type=float, default=0)
    ap.add_argument("--offset-y", type=float, default=0)
    ap.add_argument("--darken", type=float, default=0.25)
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.accent is None:  # la miniature suit la meme DA que la video (un seul accent)
        a.accent = load_config(a.work_dir).get("da", {}).get("accent", "#FFE500")
    data = load_json(os.path.join(a.work_dir, "words.json"))
    video = data["video"]
    if a.candidates:
        candidates(a.work_dir, video)
    else:
        if not a.title:
            die("--title obligatoire (mots en *etoiles* = accent).")
        compose(a.work_dir, video, a)


if __name__ == "__main__":
    main()
