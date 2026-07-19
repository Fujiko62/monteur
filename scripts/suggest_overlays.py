"""Cerveau AUTONOME : lit la transcription et propose tout seul les animations adaptees
(stat, calendar, bars, diagram, image, + memes si ton fun), en time_base original.

Detecte le TON (fun vs pro) automatiquement, puis place les overlays selon le SENS des
phrases. Regle theyo appliquee : "si la phrase n'a pas besoin d'animation, ca sert a rien
d'en mettre" -> DOUBLE SIGNAL exige (pattern + marqueur d'importance), budget parcimonieux,
et chaque suggestion porte un champ _reason (la phrase source) pour le triage.

Sortie : <work_dir>/overlays.suggested.json — une PROPOSITION a relire (chaque item doit
etre verifie a l'image avant d'etre garde : REGLE DES YEUX), puis renommer overlays.json.

Usage: python suggest_overlays.py <work_dir> [--tone auto|fun|pro] [--max-per-min 2]
"""
import argparse
import os
import re
import unicodedata
from common import log, save_json, load_json, load_config


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return t.lower()


FUN_WORDS = ["gg", "wesh", "lol", "mdr", "carapace", "kart", "win", "boss", "noob", "rage",
             "gg", "stream", "gameplay", "manette", "boost", "frag", "clutch", "malade", "cheat"]
PRO_WORDS = ["strategie", "business", "produit", "client", "chiffre", "croissance", "marche",
             "resultat", "methode", "process", "modele", "ia", "outil", "automatis", "workflow",
             "presentation", "demo", "fonctionnalite", "roadmap", "objectif"]
FAIL_WORDS = ["rate", "raté", "merde", "bug", "perdu", "nul", "enfonce", "oups", "aie", "fail"]
HYPE_WORDS = ["win", "gagne", "gagné", "premier", "victoire", "gg", "incroyable", "enorme", "record"]
FAIL_SOUNDS = ["record_scratch", "sad_trombone", "bruh"]
HYPE_SOUNDS = ["airhorn", "vine_boom", "ding"]
GROWTH_WORDS = ["augment", "croissance", "plus de", "double", "triple", "explos", "progress", "monte"]
PROCESS_WORDS = ["etape", "d'abord", "ensuite", "premierement", "deuxiem", "puis enfin", "process", "pipeline"]
DATE_RE = re.compile(r"\b(\d+)\s*(jour|jours|semaine|semaines|mois|an|ans|heure|heures)\b", re.I)
MONTH_RE = re.compile(r"\b(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\b", re.I)
NUM_RE = re.compile(r"\b(\d{1,3})\s*(%|pour ?cent|euros?|€|k|millions?|m)\b", re.I)


def detect_tone(segments):
    txt = norm(" ".join(s.get("text", "") for s in segments))
    fun = sum(txt.count(w) for w in FUN_WORDS)
    pro = sum(txt.count(w) for w in PRO_WORDS)
    return "fun" if fun >= pro else "pro"


def suggest(segments, tone, max_per_min, duration, emphasis_kw=(), lexicon=()):
    overlays, sfx_extra, zoom_extra = [], [], []
    budget = max(1, int((duration / 60) * max_per_min))
    used = 0
    last_t = -999
    last_fail_t = -999
    fail_streak = 0
    combos = 0  # combo "enchainement de malchance" : boom repete. MAX 2 par video.
    brands_used = set()
    brand_count = 0

    def ok(t):
        return t - last_t > 6 and used < budget

    def important(txt, n):
        """DOUBLE SIGNAL theyo : un pattern seul ne suffit pas, il faut aussi un marqueur
        d'importance — mot d'emphase de la config, phrase courte (punchline) ou ponctuation
        forte. Sinon '3 euros' dans un aparte neutre declencherait une stat-card."""
        if any(k in n for k in emphasis_kw):
            return True
        wc = len(txt.split())
        return wc <= 12 or txt.strip().endswith(("!", "?"))

    for s in segments:
        t = s["start"]
        txt = s.get("text", "")
        n = norm(txt)
        if not ok(t):
            continue
        placed = False
        why = txt.strip()[:90]

        m = NUM_RE.search(txt)
        d = DATE_RE.search(txt)
        mo = MONTH_RE.search(n)
        brand = next((b for b in lexicon if b in n.split() and b not in brands_used), None)
        if tone == "pro" and m and important(txt, n):
            val = m.group(1) + ("%" if "%" in m.group(2) or "cent" in m.group(2).lower() else "")
            overlays.append({"type": "stat", "value": val, "fill": min(100, int(m.group(1))),
                             "split": True, "start": round(t, 2), "dur": 3.0,
                             "_reason": f"chiffre cle: \"{why}\""})
            placed = True
        elif tone == "pro" and (d or mo) and important(txt, n):
            hl = int(d.group(1)) if d else 7
            month = (mo.group(1).upper() if mo else "").strip() or "MOIS"
            overlays.append({"type": "calendar", "month": month, "days": 30,
                             "highlight": min(30, hl), "split": True, "start": round(t, 2), "dur": 3.0,
                             "_reason": f"duree/frequence: \"{why}\""})
            placed = True
        elif tone == "pro" and any(w in n for w in GROWTH_WORDS) and important(txt, n):
            overlays.append({"type": "bars", "title": "", "bars": [{"h": 0.3}, {"h": 0.55}, {"h": 0.8}, {"h": 1}],
                             "split": True, "start": round(t, 2), "dur": 3.0,
                             "_reason": f"croissance: \"{why}\""})
            placed = True
        elif tone == "pro" and any(w in n for w in PROCESS_WORDS) and important(txt, n):
            overlays.append({"type": "diagram", "title": "", "split": True, "start": round(t, 2), "dur": 3.2,
                             "nodes": [{"id": "a", "label": "1", "x": 0.72, "y": 0.35},
                                       {"id": "b", "label": "2", "x": 0.72, "y": 0.55},
                                       {"id": "c", "label": "3", "x": 0.72, "y": 0.75}],
                             "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
                             "_reason": f"process/etapes: \"{why}\""})
            placed = True
        elif tone == "pro" and brand and brand_count < 2 and important(txt, n):
            # l'exemple canonique du plan : "si je parle de Claude, c'est interessant de
            # mettre une animation pour illustrer". type todo_image = INERTE au rendu :
            # Claude doit chercher l'image (fetch_media/screenshot_web), REGARDER la frame,
            # puis convertir en {"type":"image","src":...} — jamais de telechargement aveugle.
            overlays.append({"type": "todo_image", "_query": f"{brand} logo",
                             "mode": "card", "split": True, "start": round(t, 2), "dur": 2.6,
                             "_reason": f"marque/outil nomme: \"{why}\""})
            brands_used.add(brand)
            brand_count += 1
            placed = True
        elif tone == "fun" and any(w in n for w in FAIL_WORDS):
            # serie de fails rapprochee (<25s) -> COMBO : le MEME boom repete en rafale
            # (gag "enchainement de malchance"). Rare : max 2 par video.
            fail_streak = fail_streak + 1 if (t - last_fail_t) < 25 else 1
            last_fail_t = t
            if fail_streak >= 2 and combos < 2:
                combos += 1
                for k in range(3):
                    sfx_extra.append({"t": round(t + k * 0.45, 2), "sound": "vine_boom",
                                      "no_vary": True, "gain_db": -12 + k * 2})
                zoom_extra.append({"start": round(t - 0.1, 2), "end": round(t + 1.8, 2),
                                   "scale": 1.3, "progressive": True})
            else:
                snd = FAIL_SOUNDS[len(sfx_extra) % len(FAIL_SOUNDS)]  # variation
                sfx_extra.append({"t": round(t, 2), "sound": snd})
                zoom_extra.append({"start": round(t - 0.1, 2), "end": round(t + 2.4, 2), "scale": 1.25, "progressive": True})
            # punchline courte -> callout meme avec la VRAIE citation
            wcount = len(txt.split())
            if 2 <= wcount <= 9:
                overlays.append({"type": "callout", "text": txt.strip().upper()[:40], "emoji": "💀",
                                 "pos": "top", "start": round(t, 2), "dur": 2.2, "bg": "#111"})
            placed = True
        elif tone == "fun" and any(w in n for w in HYPE_WORDS):
            snd = HYPE_SOUNDS[len(sfx_extra) % len(HYPE_SOUNDS)]
            sfx_extra.append({"t": round(t, 2), "sound": snd})
            zoom_extra.append({"start": round(t, 2), "end": round(t + 1.2, 2), "scale": 1.12})
            placed = True

        if placed:
            used += 1
            last_t = t

    return overlays, sfx_extra, zoom_extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--tone", default="auto", choices=["auto", "fun", "pro"])
    ap.add_argument("--max-per-min", type=float, default=2,
                    help="budget d'animations/min (parcimonie theyo, defaut 2)")
    a = ap.parse_args()
    data = load_json(os.path.join(a.work_dir, "words.json"))
    cfg = load_config(a.work_dir)
    segments = data.get("segments", [])
    tone = a.tone if a.tone != "auto" else detect_tone(segments)
    log(f"ton detecte : {tone}")
    emphasis_kw = [norm(k) for k in cfg.get("motion", {}).get("emphasis_keywords", [])]
    lexicon = {norm(k) for k in cfg.get("captions", {}).get("lexicon", {})}
    ov, sx, zx = suggest(segments, tone, a.max_per_min, data.get("duration", 60),
                         emphasis_kw, lexicon)
    out = {"time_base": "original", "_tone": tone, "_review_required": True,
           "_note": "PROPOSITION. Chaque item: verifier la frame (REGLE DES YEUX), ajuster "
                    "ou supprimer, resoudre les todo_image, puis renommer en overlays.json.",
           "overlays": ov, "sfx_extra": sx, "zoom_extra": zx}
    dst = os.path.join(a.work_dir, "overlays.suggested.json")
    save_json(dst, out)
    log(f"propose : {len(ov)} animations, {len(sx)} sfx, {len(zx)} zooms -> overlays.suggested.json")
    log("PROPOSITION a trier : relis chaque _reason, regarde les frames, puis overlays.json.")


if __name__ == "__main__":
    main()
