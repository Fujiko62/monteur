"""Fabrique un SHORT vertical 9:16 depuis une longue video : PAS un moment aleatoire —
un extrait AUTONOME (debut/fin de phrase, contexte complet), avec hook a l'ecran,
sous-titres mot-a-mot (les sous-titres, c'est POUR les shorts) et CTA de fin
("la video complete est sur la chaine").

Usage:
  python make_short.py <work_dir> --start 120 --end 155 --hook "IL A VRAIMENT FAIT CA ?!"
  python make_short.py <work_dir> --auto            # choisit le meilleur moment tout seul
  python make_short.py <work_dir> --from-brief 0    # utilise meilleurs_shorts[0] de brief.json
Options : --cta "..." --layout crop|blur --out <mp4> --name <suffixe>
<work_dir> doit contenir words.json (donc transcription deja faite).
"""
import argparse
import os
import re
import sys
import unicodedata
from common import FFMPEG, ROOT, run, log, die, save_json, load_json, load_config, project_dir, safe_name, apply_caption_preset

DEFAULT_CTA = "LA VIDÉO COMPLÈTE EST SUR LA CHAÎNE 👆"
HOOK_WORDS = ["merde", "bug", "incroyable", "jamais", "record", "win", "perdu", "secret",
              "fou", "enorme", "premier", "impossible", "attention", "regarde"]


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return t.lower()


def snap_to_sentences(segments, start, end):
    """Etend [start,end] aux frontieres de phrases (contexte complet, pas de coupe seche)."""
    s2, e2 = start, end
    for seg in segments:
        if seg["start"] <= start <= seg["end"]:
            s2 = seg["start"]
        if seg["start"] <= end <= seg["end"]:
            e2 = seg["end"]
    # si le segment precedent finit sans ponctuation, remonter d'un segment (contexte)
    for i, seg in enumerate(segments):
        if abs(seg["start"] - s2) < 0.01 and i > 0:
            prev = segments[i - 1]
            if not re.search(r"[.!?…]\s*$", prev.get("text", "")) and (s2 - prev["start"]) < 12:
                s2 = prev["start"]
            break
    return max(0.0, s2 - 0.30), e2 + 0.35


def auto_pick(segments):
    """Choisit la meilleure fenetre COURTE (8-20s) : score mots forts + phrase complete.
    Regle utilisateur : un short <= 20s, plus court = mieux. On borne dur a 20s."""
    best, best_score = None, -1
    n = len(segments)
    for i in range(n):
        t0 = segments[i]["start"]
        j = i
        score = 0
        while j < n and segments[j]["end"] - t0 < 20:
            txt = norm(segments[j].get("text", ""))
            score += sum(2 for w in HOOK_WORDS if w in txt)
            score += txt.count("!") + txt.count("?")
            dur = segments[j]["end"] - t0
            if 8 <= dur <= 20 and re.search(r"[.!?…]\s*$", segments[j].get("text", "")):
                s = score + (2 if re.match(r"^[A-Z]", segments[i].get("text", " ").strip() or " ") else 0)
                if s > best_score:
                    best_score, best = s, (t0, segments[j]["end"], i, j)
            j += 1
    if not best:
        die("aucune fenetre 8-20s trouvee — donne --start/--end.")
    t0, t1, i, j = best
    # hook = segment le plus "fort" de la fenetre, court
    hook = ""
    for k in range(i, j + 1):
        txt = segments[k].get("text", "").strip()
        if 2 <= len(txt.split()) <= 9 and any(w in norm(txt) for w in HOOK_WORDS):
            hook = txt.upper()[:44]
            break
    return t0, t1, hook or "ATTENDS LA FIN 😳"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--from-brief", type=int, default=None, metavar="N")
    ap.add_argument("--hook", default=None)
    ap.add_argument("--cta", default=DEFAULT_CTA)
    ap.add_argument("--layout", default="blur", choices=["crop", "blur"])
    ap.add_argument("--name", default="short")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    data = load_json(os.path.join(a.work_dir, "words.json"))
    cfg = load_config(a.work_dir)
    segments = data.get("segments", [])
    video = data["video"]
    hook = a.hook

    if a.from_brief is not None:
        brief = load_json(os.path.join(a.work_dir, "brief.json"))
        cand = brief["meilleurs_shorts"][a.from_brief]
        start, end = float(cand["start"]), float(cand["end"])
        hook = hook or cand.get("hook", "").upper()[:44]
    elif a.auto:
        start, end, auto_hook = auto_pick(segments)
        hook = hook or auto_hook
    elif a.start is not None and a.end is not None:
        start, end = a.start, a.end
    else:
        die("donne --start/--end, --auto, ou --from-brief N.")

    start, end = snap_to_sentences(segments, start, end)
    dur = end - start
    log(f"extrait: {start:.1f}s -> {end:.1f}s ({dur:.1f}s), hook: {hook!r}")
    if dur > 20.5:
        log(f"  ATTENTION short = {dur:.1f}s > 20s. Regle utilisateur : <=20s, plus court "
            f"= mieux. Resserre --start/--end sur le SEUL beat qui frappe, sauf si chaque "
            f"seconde au-dela le merite vraiment.")

    short_dir = os.path.join(a.work_dir, f"{a.name}")
    os.makedirs(short_dir, exist_ok=True)
    cut = os.path.join(short_dir, "cut.mp4")
    fps = cfg["render"]["fps"]

    # conversion verticale 1080x1920
    if a.layout == "crop":
        vf = f"fps={fps},crop=ih*9/16:ih,scale=1080:1920,setsar=1"
    else:  # blur : video entiere au centre + fond flou (pro, ne coupe rien)
        vf = (f"fps={fps},split=2[bg][fg];"
              f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
              f"crop=1080:1920,gblur=sigma=24,eq=brightness=-0.08[b];"
              f"[fg]scale=1080:-2[f];[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1")
    run([FFMPEG, "-y", "-ss", f"{start:.3f}", "-i", video, "-t", f"{dur:.3f}",
         "-filter_complex", vf, "-af",
         "afade=t=in:d=0.03,loudnorm=I=-16:TP=-1.5:LRA=11",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", str(cfg["render"]["crf"]),
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", cfg["render"]["audio_bitrate"], cut])

    # sous-titres mot-a-mot (OUI dans un short) recales sur l'extrait
    caps = []
    for w in data["words"]:
        mid = (w["start"] + w["end"]) / 2
        if start <= mid <= end:
            caps.append({"w": w["w"], "start": round(max(0, w["start"] - start), 3),
                         "end": round(min(dur, w["end"] - start), 3)})

    capcfg = apply_caption_preset(dict(cfg["captions"]))
    # blur : la video occupe la bande centrale -> sous-titres DESSOUS (zone floue),
    # lisibles sans masquer l'action. crop : plein cadre -> centre classique.
    capcfg["position"] = "bottom" if a.layout == "blur" else "center"
    capcfg.setdefault("max_words_per_line", 3)
    capcfg["mode"] = "always"
    overlays = []
    if hook:
        overlays.append({"type": "callout", "text": hook, "emoji": "🔥", "pos": "top",
                         "start": 0.25, "dur": min(3.2, dur * 0.25), "bg": "#111"})
    overlays.append({"type": "callout", "text": a.cta, "pos": "top",
                     "start": max(0.5, dur - 3.2), "dur": 3.0, "bg": "#b00", "color": "#fff"})
    overlays.append({"type": "subscribe", "start": max(0.5, dur - 3.4), "dur": 3.2})
    sfx = [{"t": 0.0, "sound": "riser", "gain_db": -16}]

    props = {"video": "cut.mp4", "width": 1080, "height": 1920, "fps": fps,
             "durationInFrames": max(1, int(round(dur * fps))),
             "captions": caps, "zooms": [], "sfx": sfx, "overlays": overlays,
             "config": {"captions": capcfg, "sfx": cfg["sfx"], "motion": cfg["motion"],
                        "overlays": cfg.get("overlays", {}), "cta": cfg.get("cta", {})}}
    save_json(os.path.join(short_dir, "props.json"), props)

    shorts_dir = os.path.join(project_dir(video), "shorts")
    os.makedirs(shorts_dir, exist_ok=True)
    out = a.out or os.path.join(shorts_dir, f"short-{a.name}.mp4")
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "render.py"),
                        short_dir, out])
    if r.returncode != 0:
        die("rendu du short echoue.")
    log(f"SHORT PRET: {out}")


if __name__ == "__main__":
    main()
