"""Coupe + couleur + audio, puis remappe mots -> timeline coupee et genere
sous-titres / bruitages / zooms.

Usage: python build_cut.py <work_dir>
Entree : words.json, plan.json, config.json
Sortie : <work_dir>/cut.mp4, captions.json, cues.json, props.json
"""
import argparse
import os
import re
import tempfile
from common import FFMPEG, run, log, die, save_json, load_json, load_config, ffprobe_info, apply_caption_preset


def analyze_luma(video):
    """Luma moyenne (0-255) par echantillonnage via signalstats (lu sur stderr)."""
    r = run([FFMPEG, "-y", "-i", video,
             "-vf", "fps=2,scale=96:-1,signalstats,metadata=mode=print",
             "-an", "-f", "null", "-"])
    vals = []
    for line in (r.stderr or "").splitlines():
        m = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", line)
        if m:
            vals.append(float(m.group(1)))
    return sum(vals) / len(vals) if vals else 128.0


def color_filter(video, cfg):
    c = cfg["color"]
    if not c.get("auto_correct", True):
        return None, None
    mean = analyze_luma(video)
    target = c.get("target_luma", 118)
    ratio = target / max(mean, 1.0)
    gamma = max(0.72, min(c.get("max_gain", 1.35), ratio))
    sat = c.get("saturation", 1.05)
    # eq: gamma > 1 eclaircit les tons moyens ; saturation legere
    return f"eq=gamma={gamma:.3f}:saturation={sat:.3f}", mean


def cut_segments(video, segs, fps, out_w, out_h, color, do_scale, has_audio, crf, abitrate, wd):
    """Decoupe chaque segment dans son propre fichier (seek rapide + reencode precis)
    puis concatene. Scalable a des centaines de segments, sans bufferiser la source."""
    import glob as _glob
    segdir = os.path.join(wd, "segs")
    os.makedirs(segdir, exist_ok=True)
    for old in _glob.glob(os.path.join(segdir, "*.mp4")):
        os.remove(old)

    vf = [f"fps={fps}"]
    if do_scale:
        vf.append(f"scale={out_w}:{out_h}")
    vf.append("setsar=1")
    if color:
        vf.append(color)
    vf.append("format=yuv420p")
    vfs = ",".join(vf)

    lines = []
    durations = []
    for i, s in enumerate(segs):
        dur = s["end"] - s["start"]
        speed = float(s.get("speed", 1.0))
        seg = os.path.abspath(os.path.join(segdir, f"seg_{i:04d}.mp4"))
        # timescale commune multiple du fps : le concat -c copy garde des timestamps
        # EXACTS (sinon avg_fps derive de 30 -> Remotion "No frame found at position").
        # speed != 1 : accelere (timelapse) ou ralenti. setpts AVANT fps pour que le
        # filtre fps re-echantillonne proprement les frames retimees.
        seg_vfs = vfs if speed == 1.0 else f"setpts=PTS/{speed:.4f}," + vfs
        out_dur = dur / speed
        # -t COTE ENTREE (avant -i) : indispensable avec setpts, sinon -t limite la
        # sortie et ffmpeg lit dur*speed secondes de source (segment accelere trop long).
        cmd = [FFMPEG, "-y", "-ss", f"{s['start']:.3f}", "-t", f"{dur:.3f}", "-i", video,
               "-vf", seg_vfs, "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", "-video_track_timescale", "15360"]
        if has_audio:
            # micro-fondus 25ms en tete/queue de chaque segment : coupes audio douces,
            # sans clics ni consonnes tranchees (montage pro).
            af = []
            if speed != 1.0:
                # atempo accepte [0.5, 2.0] par etage -> on chaine.
                r = speed
                while r > 2.0:
                    af.append("atempo=2.0"); r /= 2.0
                while r < 0.5:
                    af.append("atempo=0.5"); r /= 0.5
                af.append(f"atempo={r:.4f}")
                if speed >= 3.0 or s.get("mute"):
                    # timelapse : la voix chipmunk est ridicule -> silence (la musique
                    # de fond ajoutee apres remplit le trou).
                    af.append("volume=0")
            fout = max(0.0, out_dur - 0.030)
            af += ["afade=t=in:st=0:d=0.025", f"afade=t=out:st={fout:.3f}:d=0.030"]
            cmd += ["-af", ",".join(af), "-c:a", "aac", "-b:a", abitrate, "-ac", "2"]
        else:
            cmd += ["-an"]
        cmd += [seg]
        run(cmd)
        durations.append(ffprobe_info(seg)["duration"])
        if (i + 1) % 20 == 0:
            log(f"  ...{i+1}/{len(segs)} segments encodes")
        lines.append("file '" + seg.replace("\\", "/") + "'")

    listfile = os.path.abspath(os.path.join(wd, "concat_list.txt"))
    with open(listfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    cut = os.path.join(wd, "cut.mp4")
    ccmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c:v", "copy",
            "-video_track_timescale", "15360"]
    if has_audio:
        ccmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", abitrate]
    ccmd += ["-movflags", "+faststart", cut]
    run(ccmd)
    for old in _glob.glob(os.path.join(segdir, "*.mp4")):
        os.remove(old)
    return cut, durations


def apply_lexicon(caps, cfg):
    """Corrige les mots que la transcription rate systematiquement (noms propres, marques).
    Point cle de theyo : 'anthropique' au lieu d'Anthropic, 'cloud' au lieu de Claude —
    'cette difference est tres importante surtout pour les sous-titres'."""
    lex = cfg.get("captions", {}).get("lexicon", {})
    if not lex:
        return caps, 0
    n = 0
    for c in caps:
        core = c["w"]
        m = re.match(r"^(\W*)(.*?)(\W*)$", core, re.UNICODE)
        pre, word, post = m.group(1), m.group(2), m.group(3)
        rep = lex.get(word.lower())
        if rep:
            c["w"] = pre + rep + post
            n += 1
    return caps, n


def merge_tokens(caps):
    """Fusionne la ponctuation isolee et les fragments en apostrophe dans le mot precedent.
    Ex: "Salut"+"!" -> "Salut!" ; "Aujourd"+"'hui," -> "Aujourd'hui,"."""
    out = []
    for c in caps:
        core = re.sub(r"[^\w%]", "", c["w"], flags=re.UNICODE)
        cont = c["w"][:1] in ("'", "’")
        if out and (core == "" or cont):
            out[-1]["w"] += c["w"]
            out[-1]["end"] = max(out[-1]["end"], c["end"])
        else:
            out.append(dict(c))
    return out


# Pools de variation : un "son logique" -> plusieurs variantes reelles, on tourne.
SFX_POOLS = {
    "whoosh": ["whoosh", "whoosh2", "swoosh_soft", "transition2", "transition3", "whoosh3"],
    "impact": ["impact", "impact3", "boom", "boom2"],
    "pop": ["pop", "pop2", "pop3", "ding", "ding2"],
    "click": ["click", "click2", "shutter"],
    "vine_boom": ["vine_boom", "boom", "bruh"],
    "record_scratch": ["record_scratch", "sad_trombone", "bruh"],
}


def make_sfx_picker():
    """Retourne pick(name, i) qui varie les sons d'un pool, sans jamais repeter
    deux fois de suite, et n'utilise que les fichiers reellement presents."""
    sfx_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "remotion", "public", "sfx")
    have = {f[:-4] for f in os.listdir(sfx_dir)} if os.path.isdir(sfx_dir) else set()
    counters = {}
    last = {}

    def pick(name, _i=None):
        pool = [s for s in SFX_POOLS.get(name, [name]) if s in have] or [name]
        k = counters.get(name, 0)
        choice = pool[k % len(pool)]
        if choice == last.get(name) and len(pool) > 1:
            k += 1
            choice = pool[k % len(pool)]
        counters[name] = k + 1
        last[name] = choice
        return choice

    return pick


def remap_time(t, segs, offsets):
    for i, s in enumerate(segs):
        if s["start"] <= t <= s["end"]:
            return offsets[i] + (t - s["start"]) / float(s.get("speed", 1.0))
    return None


def seg_speed_at(t, segs):
    for s in segs:
        if s["start"] <= t <= s["end"]:
            return float(s.get("speed", 1.0))
    return 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--skip-cut", action="store_true",
                    help="reutilise cut.mp4 + offsets.json existants (regenere seulement "
                         "sous-titres/bruitages/zooms/overlays) : boucle de review rapide")
    a = ap.parse_args()
    wd = a.work_dir
    data = load_json(os.path.join(wd, "words.json"))
    plan = load_json(os.path.join(wd, "plan.json"))
    cfg = load_config(wd)
    segs = plan["keep_segments"]
    if not segs:
        die("plan vide.")

    fps = cfg["render"]["fps"]
    w, h = data["width"], data["height"]
    # downscale optionnel (ex: 1440p -> 1080p) pour un rendu long faisable
    scale_h = cfg["render"].get("scale_to_height")
    do_scale = bool(scale_h) and h > scale_h
    if do_scale:
        out_w = int(round(w * scale_h / h / 2)) * 2
        out_h = int(scale_h)
        log(f"downscale {w}x{h} -> {out_w}x{out_h}")
    else:
        out_w, out_h = w, h
    has_audio = data.get("has_audio", True)
    color, mean = color_filter(data["video"], cfg)
    if color:
        log(f"couleur: luma moyenne {mean:.0f} -> filtre {color}")

    offsets_path = os.path.join(wd, "offsets.json")
    if a.skip_cut and os.path.exists(os.path.join(wd, "cut.mp4")) and os.path.exists(offsets_path):
        log("--skip-cut : reutilisation de cut.mp4 + offsets existants.")
        saved = load_json(offsets_path)
        offsets, cut_dur = saved["offsets"], saved["cut_dur"]
    else:
        log(f"coupe+encodage de {len(segs)} segments (decoupe fichier par fichier + concat)...")
        _, durations = cut_segments(data["video"], segs, fps, out_w, out_h, color, do_scale,
                                    has_audio, cfg["render"]["crf"], cfg["render"]["audio_bitrate"], wd)
        # offsets construits sur les durees REELLES encodees (sous-titres cales)
        offsets = []
        acc = 0.0
        for d in durations:
            offsets.append(acc)
            acc += d
        cut_dur = acc
        save_json(offsets_path, {"offsets": offsets, "cut_dur": cut_dur})

    # sous-titres : mots dont le milieu tombe dans un segment garde
    caps = []
    for word in data["words"]:
        mid = (word["start"] + word["end"]) / 2
        ct = remap_time(mid, segs, offsets)
        if ct is None:
            continue
        # pas de sous-titres dans un segment accelere (mots illisibles/chipmunk)
        if seg_speed_at(mid, segs) >= 1.5:
            continue
        st = remap_time(word["start"], segs, offsets)
        en = remap_time(word["end"], segs, offsets)
        st = ct - 0.06 if st is None else st
        en = ct + 0.12 if en is None else en
        if en <= st:
            en = st + 0.12
        caps.append({"w": word["w"], "start": round(st, 3), "end": round(en, 3)})
    caps.sort(key=lambda x: x["start"])
    caps = merge_tokens(caps)
    caps, nlex = apply_lexicon(caps, cfg)
    if nlex:
        log(f"lexique: {nlex} mots corriges (noms propres/marques).")

    # Les sous-titres mot-a-mot, c'est un langage de SHORT. mode:
    #  "always" = toujours ; "off" = jamais ; "auto" (defaut) = OUI si vertical ou < 90s,
    #  NON sur une longue video horizontale (le texte passe par callouts/animations).
    cap_mode = cfg["captions"].get("mode", "auto")
    caps_props = caps
    if cap_mode == "off" or (cap_mode == "auto" and out_w > out_h and cut_dur > 90):
        caps_props = []
        log("sous-titres mot-a-mot DESACTIVES (longue video horizontale — langage de short). "
            "captions.mode=always pour forcer.")

    # zooms + bruitages
    zooms = []
    sfx = []
    m = cfg["motion"]
    sc = cfg["sfx"]
    pick = make_sfx_picker()
    if m.get("zoom_on_emphasis", True):
        for e in plan["emphasis"]:
            st = remap_time(e["start"], segs, offsets)
            en = remap_time(e["end"], segs, offsets)
            if st is None:
                continue
            en = (st + 0.4) if en is None else en
            zooms.append({"start": round(max(0, st - m["zoom_ease_s"]), 3),
                          "end": round(en + 0.25, 3), "scale": m["zoom_scale"]})
            if sc["enabled"] and sc.get("on_emphasis", True):
                sfx.append({"t": round(st, 3), "sound": pick(sc.get("emphasis_sound", "impact")),
                            "gain_db": sc["gain_db"]})
    # bruitage sur transition : seulement si un gros temps mort a ete retire (vrai
    # changement de scene), pas a chaque micro-coupe. cut_min_gap_s=0 -> toutes.
    cut_gap_thr = sc.get("cut_min_gap_s", 0.0)
    if sc["enabled"] and sc.get("on_cut_transition", True):
        for i in range(1, len(segs)):
            removed = segs[i]["start"] - segs[i - 1]["end"]
            if removed >= cut_gap_thr:
                sfx.append({"t": round(offsets[i], 3), "sound": pick(sc.get("cut_sound", "whoosh")),
                            "gain_db": sc["gain_db"]})
    if sc["enabled"] and sc.get("on_intro", True):
        sfx.append({"t": 0.0, "sound": sc.get("intro_sound", "riser"), "gain_db": sc["gain_db"]})
    if m.get("punch_in_on_cut", False):
        for i in range(1, len(segs)):
            if segs[i]["start"] - segs[i - 1]["end"] >= cut_gap_thr:
                off = offsets[i]
                zooms.append({"start": round(off, 3), "end": round(off + 0.22, 3),
                              "scale": 1.05, "punch": True})

    # overlays optionnels authored par le "monteur" (Claude) : images, schemas, CTA...
    # time_base:"original" -> les temps sont en timeline SOURCE et remappes ici (pratique :
    # on lit les moments directement dans la transcription).
    overlays = []
    ov_path = os.path.join(wd, "overlays.json")
    if os.path.exists(ov_path):
        ov = load_json(ov_path)
        orig = isinstance(ov, dict) and ov.get("time_base") == "original"

        def remap_key(obj, key):
            """Remappe obj[key] (temps original -> cut). Retourne False si le moment a ete
            coupe (l'appelant abandonne l'evenement pour eviter un placement aleatoire)."""
            if not orig or key not in obj:
                return True
            ct = remap_time(obj[key], segs, offsets)
            if ct is None:
                return False
            obj[key] = round(ct, 3)
            return True

        if isinstance(ov, dict):
            src_overlays = ov.get("overlays", [])
            overlays = [o for o in src_overlays if remap_key(o, "start")]
            dropped_ov = len(src_overlays) - len(overlays)
            for e in ov.get("sfx_extra", []):
                e.setdefault("gain_db", sc["gain_db"])
                if remap_key(e, "t"):
                    # no_vary=true : repetition VOULUE (ex: combo boom-boom-boom sur un
                    # enchainement de malchance) -> on ne fait pas tourner le pool.
                    if not e.pop("no_vary", False):
                        e["sound"] = pick(e["sound"])
                    sfx.append(e)
            for z in ov.get("zoom_extra", []):
                if remap_key(z, "start") and remap_key(z, "end"):
                    zooms.append(z)
            if orig and dropped_ov:
                log(f"  {dropped_ov} overlay(s) sur un moment coupe -> ignore(s).")
        elif isinstance(ov, list):
            overlays = ov
        log(f"overlays charges: {len(overlays)} elements (time_base={'original' if orig else 'cut'}).")

    save_json(os.path.join(wd, "captions.json"), caps)
    save_json(os.path.join(wd, "cues.json"),
              {"fps": fps, "width": out_w, "height": out_h, "cut_duration": round(cut_dur, 3),
               "zooms": zooms, "sfx": sfx})

    # props pour Remotion
    props = {
        "video": "cut.mp4",
        "width": out_w,
        "height": out_h,
        "fps": fps,
        "durationInFrames": max(1, int(round(cut_dur * fps))),
        "captions": caps_props,
        "zooms": zooms,
        "sfx": sfx,
        "overlays": overlays,
        "config": {
            "captions": apply_caption_preset(dict(cfg["captions"])), "sfx": cfg["sfx"], "motion": cfg["motion"],
            "overlays": cfg.get("overlays", {}), "cta": cfg.get("cta", {}),
            "da": cfg.get("da", {}), "layouts": cfg.get("layouts", {}),
        },
    }
    save_json(os.path.join(wd, "props.json"), props)
    log(f"OK: cut.mp4 ({cut_dur:.1f}s), {len(caps)} sous-titres, {len(zooms)} zooms, {len(sfx)} bruitages.")


if __name__ == "__main__":
    main()
