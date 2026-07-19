"""Cerveau du montage : construit le plan de coupe agressif + points d'accentuation.

Usage: python plan.py <work_dir>
Entree : <work_dir>/words.json  +  config.json
Sortie : <work_dir>/plan.json  (temps en timeline ORIGINALE)
"""
import argparse
import difflib
import os
import re
import sys
import unicodedata
from common import log, save_json, load_json, load_config


def normtext(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


# Calibrage du plan theyo : "soit extremement agressif, des que vous finissez le mot ca
# cutte, ou alors vous pouvez laisser plus de temps pour un ton plus naturel".
# "gentle"/"natural" = les valeurs du config.json telles quelles (le style naturel).
AGGRESSIVENESS_PRESETS = {
    "aggressive": {"min_silence_to_cut_s": 0.45, "keep_pause_after_sentence_s": 0.10,
                   "pad_end_s": 0.10, "mid_sentence_factor": 2.0},
    "natural": {},
    "gentle": {},
}


def apply_aggressiveness(cfg, work_dir):
    """Branche edit.aggressiveness (etait une cle morte). Les cles posees explicitement
    dans config.override.json gardent toujours le dernier mot."""
    e = cfg["edit"]
    name = str(e.get("aggressiveness", "gentle")).lower()
    preset = AGGRESSIVENESS_PRESETS.get(name)
    if preset is None:
        log(f"aggressiveness '{name}' inconnue (aggressive/natural/gentle) -> ignoree.")
        return
    explicit = {}
    ov = os.path.join(work_dir, "config.override.json")
    if os.path.exists(ov):
        explicit = load_json(ov).get("edit", {})
    applied = {k: v for k, v in preset.items() if k not in explicit}
    e.update(applied)
    if applied:
        log(f"preset de coupe '{name}' : " +
            ", ".join(f"{k}={v}" for k, v in applied.items()))


def overlap_s(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def silence_between(t0, t1, silences, min_overlap=0.12):
    """Le silence AUDIO detecte qui chevauche le mieux [t0,t1], sinon None.
    C'est la verification 'vrai silence' du plan (un rire/une musique n'est pas coupable)."""
    best, best_ov = None, min_overlap
    for s in silences:
        if s["start"] >= t1:
            break
        ov = overlap_s(t0, t1, s["start"], s["end"])
        if ov > best_ov:
            best, best_ov = s, ov
    return best


def drop_words_in_silences(words, keep, silences):
    """Un mot dont ~90% de la duree tombe dans un silence audio est physiquement
    impossible : hallucination whisper (anti-hallucination AMONT, complement de la regex)."""
    dropped = 0
    for i, w in enumerate(words):
        if not keep[i]:
            continue
        dur = max(0.01, w["end"] - w["start"])
        inside = sum(overlap_s(w["start"], w["end"], s["start"], s["end"]) for s in silences)
        if inside / dur >= 0.9:
            keep[i] = False
            dropped += 1
    return dropped


def remove_retakes(words, segments, keep, cfg):
    """Detecte les phrases refaites (ex: intro recommencee) et RETIRE les prises
    anterieures pour garder la DERNIERE (la plus claire)."""
    e = cfg.get("edit", {})
    if not e.get("remove_retakes", True):
        return 0
    thr = e.get("retake_similarity", 0.72)
    win = e.get("retake_window", 8)
    norms = [normtext(s.get("text", "")) for s in segments]
    drop = []
    for i in range(len(segments)):
        if len(norms[i]) < 12:
            continue
        for j in range(i + 1, min(i + 1 + win, len(segments))):
            if len(norms[j]) < 12:
                continue
            if difflib.SequenceMatcher(None, norms[i], norms[j]).ratio() >= thr:
                drop.append((segments[i]["start"], segments[i]["end"]))
                break
    dropped = 0
    for k, w in enumerate(words):
        mid = (w["start"] + w["end"]) / 2
        if keep[k] and any(a <= mid <= b for a, b in drop):
            keep[k] = False
            dropped += 1
    return dropped


def norm(w):
    w = "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9%]", "", w.lower())


def is_number(w):
    return bool(re.search(r"\d", w)) or "%" in w


# Hallucinations classiques de Whisper sur musique/silence (credits de sous-titrage,
# remerciements, etc.) -> a retirer : faux sous-titres + segments inutiles.
HALLUCINATION_RE = re.compile(
    r"sous[- ]?titr|amara\.org|r[eé]alis[eé]s? par|st'?\s*501|abonnez[- ]?vous|"
    r"merci d'avoir regard|like et abonne|n'h[eé]sitez pas|copyright|❤",
    re.I,
)


def mark_hallucinations(words, segments, keep, cfg):
    """Marque comme retires les mots situes dans un segment hallucine."""
    extra = cfg.get("edit", {}).get("drop_phrases", [])
    ranges = []
    for s in segments:
        t = s.get("text", "")
        if HALLUCINATION_RE.search(t) or any(p.lower() in t.lower() for p in extra):
            ranges.append((s["start"], s["end"]))
    if not ranges:
        return 0
    dropped = 0
    for i, w in enumerate(words):
        mid = (w["start"] + w["end"]) / 2
        if any(a <= mid <= b for a, b in ranges):
            if keep[i]:
                dropped += 1
            keep[i] = False
    return dropped


def build_keep_flags(words, cfg):
    """Retourne une liste de bool (garder ce mot ?) : filtre fillers + repetitions."""
    e = cfg["edit"]
    fillers = set(norm(f) for f in e["fillers"] if " " not in f)
    multi = [tuple(norm(x) for x in f.split()) for f in e["fillers"] if " " in f]
    n = len(words)
    keep = [True] * n
    normed = [norm(w["w"]) for w in words]

    # pseudo-mots de ponctuation pure ("...", "…") : whisper en produit sur les temps
    # morts (VAD off). Ce ne sont PAS des paroles — les garder maintient les segments
    # en vie a travers les chargements/videos regardees et EMPECHE toute coupe.
    ghosts = 0
    for i, nw in enumerate(normed):
        if not nw:
            keep[i] = False
            ghosts += 1
    if ghosts:
        log(f"pseudo-mots retires : {ghosts} tokens de ponctuation pure ('...') — "
            f"pas de la parole, les temps morts redeviennent coupables.")

    if e.get("remove_fillers", True):
        for i, nw in enumerate(normed):
            if nw and nw in fillers:
                keep[i] = False
        # fillers multi-mots
        for seq in multi:
            L = len(seq)
            for i in range(n - L + 1):
                if tuple(normed[i:i + L]) == seq:
                    for j in range(i, i + L):
                        keep[j] = False

    if e.get("remove_repetitions", True):
        # begaiements : mots identiques consecutifs -> garder le dernier
        i = 0
        while i < n:
            if not normed[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and normed[j + 1] == normed[i] and normed[i]:
                j += 1
            if j > i:
                for k in range(i, j):
                    keep[k] = False
            i = j + 1
    return keep


TERMINAL_RE = re.compile(r"[.!?…]\s*$")


def collapse_repeated_phrases(words, keep, cfg):
    """Coupe les PHRASES repetees collees (pas seulement les mots isoles) :
    'toujours plus toujours plus', 'je vais prendre l'aise ... je vais prendre l'aise',
    'un mode de mode'. On garde la DERNIERE occurrence (la prise nette), comme theyo.

    Balaye les mots gardes ; pour chaque position, cherche un n-gramme (n de max a 2) qui
    se repete juste apres (avec au plus quelques mots de liaison entre), dans une fenetre
    de temps courte -> supprime l'occurrence anterieure + la liaison."""
    e = cfg["edit"]
    if not e.get("remove_repeated_phrases", True):
        return 0
    max_n = e.get("repeat_ngram_max", 6)
    max_gap = e.get("repeat_ngram_gap_words", 2)
    max_span = e.get("repeat_max_span_s", 6.0)
    order = [i for i in range(len(words)) if keep[i]]
    nz = {i: norm(words[i]["w"]) for i in order}
    dropped = 0
    a = 0
    while a < len(order):
        matched = False
        for nn in range(max_n, 1, -1):
            if a + nn > len(order):
                continue
            first = [nz[order[a + k]] for k in range(nn)]
            if any(x == "" for x in first):
                continue
            for gap in range(0, max_gap + 1):
                b = a + nn + gap
                if b + nn > len(order):
                    break
                second = [nz[order[b + k]] for k in range(nn)]
                if first != second:
                    continue
                span = words[order[b + nn - 1]]["end"] - words[order[a]]["start"]
                if span > max_span:
                    continue
                for k in range(a, b):  # jette la 1re prise + les mots de liaison
                    keep[order[k]] = False
                    dropped += 1
                a = b
                matched = True
                break
            if matched:
                break
        if not matched:
            a += 1
    return dropped


def remove_false_starts(words, keep, cfg):
    """Coupe les phrases NON FINIES reprises (faux departs) : une amorce courte, sans
    ponctuation finale, immediatement REPRISE avec le(s) meme(s) premier(s) mot(s) de
    contenu -> on jette l'amorce, on garde la reprise complete. Ex : 'alors c'est parti
    pour le... alors c'est parti pour une map'."""
    e = cfg["edit"]
    if not e.get("remove_false_starts", True):
        return 0
    max_words = e.get("false_start_max_words", 8)
    gap_s = e.get("false_start_clause_gap_s", 0.45)
    fillers_set = set(norm(f) for f in e.get("fillers", []) if " " not in f)
    order = [i for i in range(len(words)) if keep[i]]
    if not order:
        return 0
    # decoupe en clauses : coupe apres ponctuation finale OU gap de silence
    clauses, cur = [], [order[0]]
    for idx in order[1:]:
        prev = cur[-1]
        if TERMINAL_RE.search(words[prev]["w"]) or (words[idx]["start"] - words[prev]["end"] > gap_s):
            clauses.append(cur)
            cur = [idx]
        else:
            cur.append(idx)
    clauses.append(cur)

    def content_tokens(cl):
        return [norm(words[i]["w"]) for i in cl
                if norm(words[i]["w"]) and norm(words[i]["w"]) not in fillers_set]

    dropped = 0
    for a in range(len(clauses) - 1):
        A, B = clauses[a], clauses[b := a + 1]
        if not A:
            continue
        if TERMINAL_RE.search(words[A[-1]]["w"]):
            continue  # A est finie -> pas un faux depart
        ca, cb = content_tokens(A), content_tokens(B)
        if not ca or not cb:
            continue
        if len(ca) > max_words or len(ca) >= len(cb):
            continue  # A doit etre une amorce courte, plus breve que la reprise
        # reprise du meme debut : soit meme 1er mot de contenu (amorce <=4 mots), soit
        # les 2 memes premiers mots (amorce plus longue). C'est le faux depart theyo.
        need = 1 if len(ca) <= 4 else 2
        need = min(need, len(ca), len(cb))
        if ca[:need] == cb[:need]:
            for i in A:
                if keep[i]:
                    keep[i] = False
                    dropped += 1
    return dropped


def build_segments(words, keep, cfg, silences=None):
    """Assemble les segments a garder en collapsant les silences longs.

    Avec le detecteur de silence (plan theyo) : un gap whisper n'est coupe QUE s'il
    correspond a un vrai silence audio, et les bornes de coupe sont snappees sur les
    bords du silence (coupes "extremement precises" du plan)."""
    e = cfg["edit"]
    thr = e["min_silence_to_cut_s"]
    pad_s = e.get("pad_start_s", 0.04)
    pad_e = e.get("pad_end_s", 0.06)
    keep_pause = e.get("keep_pause_after_sentence_s", 0.18)
    silences = silences if (silences and e.get("use_silence_detector", True)) else []
    protected = [(float(p["start"]), float(p["end"]))
                 for p in (e.get("keep_silences") or [])]

    # Protection milieu de phrase : on coupe volontiers APRES une fin de phrase (. ! ? …),
    # mais en plein milieu d'une phrase il faut un blanc nettement plus long. C'est ce qui
    # evite les coupes "a cote de la plaque" qui hachent le discours.
    midf = e.get("mid_sentence_factor", 1.8)

    def ends_sentence(w):
        return bool(re.search(r"[.!?…]\s*$", w))

    kept = [i for i, k in enumerate(keep) if k]
    if not kept:
        return []
    segs = []
    cur_start = words[kept[0]]["start"] - pad_s
    cur_end = words[kept[0]]["end"]
    prev = kept[0]
    skipped_no_silence = 0
    for idx in kept[1:]:
        gap = words[idx]["start"] - words[prev]["end"]
        dropped_between = (idx - prev) > 1  # des mots (fillers/reps) ont ete retires
        eff_thr = thr if ends_sentence(words[prev]["w"]) else thr * midf
        do_cut = gap > eff_thr or dropped_between
        # silence voulu (pause dramatique) declare dans edit.keep_silences -> on ne coupe pas
        if do_cut and not dropped_between and protected and any(
                overlap_s(words[prev]["end"], words[idx]["start"], p0, p1) > 0.05
                for p0, p1 in protected):
            do_cut = False
        # verification "vrai silence" : un gap COURT sans silence audio = rire/respiration
        # -> on ne coupe pas (proteger le non-verbal). Mais un gap LONG (chargement, video
        # regardee, temps mort) se coupe QUOI QU'IL ARRIVE : le son du jeu qui remplit le
        # blanc n'est pas une raison de garder 20s de rien. (Les gaps crees par des mots
        # retires sont coupes aussi : le contenu est deja marque a retirer.)
        protect_max = e.get("silence_protect_max_gap_s", 3.0)
        sil = silence_between(words[prev]["end"] - 0.05, words[idx]["start"] + 0.05,
                              silences) if (do_cut and silences) else None
        if (do_cut and not dropped_between and silences and sil is None
                and gap <= protect_max):
            do_cut = False
            skipped_no_silence += 1
        if do_cut:
            end = cur_end + min(keep_pause, gap / 2 if gap > 0 else keep_pause)
            start = words[idx]["start"] - pad_s
            if sil:  # snap sur le silence reel : fin nette, reprise juste avant la voix
                end = min(end, max(cur_end, sil["start"]) + 0.06)
                start = max(start, min(sil["end"], words[idx]["start"]) - 0.08)
            segs.append([max(0, cur_start), end])
            cur_start = start
        cur_end = words[idx]["end"]
        prev = idx
    segs.append([max(0, cur_start), cur_end + pad_e])
    if skipped_no_silence:
        log(f"detecteur de silence : {skipped_no_silence} coupes annulees "
            f"(gap sans vrai silence audio : rire/respiration/ambiance gardes).")
    # nettoyage : fusionne les segments qui se chevauchent apres padding
    segs.sort()
    merged = [segs[0]]
    for s, en in segs[1:]:
        if s <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], en)
        else:
            merged.append([s, en])

    # EXCISION des mots jetes : marquer keep=False ne suffit pas — le lead-in (pad_s) et la
    # fusion peuvent re-avaler un mot retire coince entre deux mots gardes. On carve donc le
    # temps EXACT des mots retires hors des segments (comme boring.json). C'est ce qui fait
    # vraiment disparaitre repetitions/fillers/faux departs du montage ET des sous-titres.
    dead = []
    for i, k in enumerate(keep):
        if k:
            continue
        a, b = words[i]["start"], words[i]["end"]
        if b - a < 0.02:
            continue
        if dead and a <= dead[-1][1] + 0.06:
            dead[-1][1] = max(dead[-1][1], b)
        else:
            dead.append([a, b])
    if dead:
        out = []
        for s, en in merged:
            cuts = [d for d in dead if d[1] > s and d[0] < en]
            if not cuts:
                out.append([s, en])
                continue
            pos = s
            for d0, d1 in cuts:
                # petite marge (25ms) pour ne pas raboter la consonne du mot voisin garde
                lo, hi = max(s, d0 + 0.025), min(en, d1 - 0.025)
                if hi <= lo:
                    continue
                if lo - pos > 0.12:
                    out.append([pos, lo])
                pos = max(pos, hi)
            if en - pos > 0.12:
                out.append([pos, en])
        merged = out

    # ANTI-HACHAGE : une coupe qui ne retire QUE du petit silence (< min_pure_silence_cut_s,
    # aucun mot jete dedans) n'apporte rien et hache le discours (mesure par ears.py :
    # 222 coupes/10min = jonctions degradees). On re-fusionne ces micro-coupes : le blanc
    # reste, le rythme respire. Les excisions de mots (repetitions, fillers) sont GARDEES.
    min_pure = e.get("min_pure_silence_cut_s", 0.6)
    if min_pure > 0 and len(merged) > 1:
        fused = [merged[0]]
        unhached = 0
        for s, en in merged[1:]:
            gap0, gap1 = fused[-1][1], s
            gap_len = gap1 - gap0
            has_dead = any(overlap_s(gap0, gap1, d0, d1) > 0.03 for d0, d1 in dead)
            if 0 < gap_len < min_pure and not has_dead:
                fused[-1][1] = en
                unhached += 1
            else:
                fused.append([s, en])
        if unhached:
            log(f"anti-hachage : {unhached} micro-coupes de silence pur re-fusionnees "
                f"(<{min_pure}s, le blanc reste, le discours respire).")
        merged = fused

    return [{"start": round(s, 3), "end": round(en, 3)} for s, en in merged if en - s > 0.12]


def find_emphasis(words, keep, cfg):
    """Zooms SELECTIFS (plan theyo : "comprendre quand est-ce qu'il faut PAS mettre de
    zoom"). Un mot-cle dans une phrase neutre ne merite rien : on exige un signal de
    punchline (pause apres le mot ou fin de phrase proche), on espace les zooms et on
    plafonne leur nombre — sinon 15 "Claude" = 15 zooms mecaniques."""
    mcfg = cfg["motion"]
    kw = set(norm(k) for k in mcfg["emphasis_keywords"])
    on_num = mcfg.get("emphasis_on_numbers", True)
    min_gap = mcfg.get("emphasis_min_gap_s", 8.0)
    per_min = mcfg.get("max_zooms_per_min", 4)
    require_punch = mcfg.get("emphasis_require_punch", True)
    kept_idx = [i for i, k in enumerate(keep) if k]
    dur = words[kept_idx[-1]]["end"] if kept_idx else 0
    budget = max(2, int(dur / 60.0 * per_min)) if per_min else 10**9

    def punchy(i):
        """Pause apres le mot OU fin de phrase dans les 3 mots suivants = accent naturel."""
        nxt = [j for j in kept_idx if j > i][:3]
        if not nxt:
            return True
        if words[nxt[0]]["start"] - words[i]["end"] > 0.25:
            return True
        return any(re.search(r"[.!?…]\s*$", words[j]["w"]) for j in nxt)

    out = []
    last_t = -1e9
    last_by_word = {}
    skipped = 0
    for i, w in enumerate(words):
        if not keep[i]:
            continue
        nw = norm(w["w"])
        reason = None
        if nw and nw in kw:
            reason = "keyword"
        elif on_num and is_number(w["w"]):
            reason = "number"
        if not reason:
            continue
        if (w["start"] - last_t < min_gap or len(out) >= budget or
                (nw in last_by_word and w["start"] - last_by_word[nw] < min_gap * 3) or
                (require_punch and reason == "keyword" and not punchy(i))):
            skipped += 1
            continue
        out.append({"start": w["start"], "end": w["end"], "word": w["w"], "reason": reason})
        last_t = w["start"]
        last_by_word[nw] = w["start"]
    if skipped:
        log(f"zooms selectifs : {skipped} accentuations ignorees "
            f"(phrase neutre / trop proche / budget {budget}).")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    a = ap.parse_args()
    data = load_json(os.path.join(a.work_dir, "words.json"))
    cfg = load_config(a.work_dir)
    words = data["words"]
    if not words:
        log("aucun mot transcrit : plan = video entiere.")
        plan = {"keep_segments": [{"start": 0, "end": data["duration"]}], "emphasis": [], "stats": {}}
        save_json(os.path.join(a.work_dir, "plan.json"), plan)
        return

    apply_aggressiveness(cfg, a.work_dir)
    silences = data.get("silences") or []
    keep = build_keep_flags(words, cfg)
    segments = data.get("segments", [])
    if silences and cfg["edit"].get("use_silence_detector", True):
        ghost = drop_words_in_silences(words, keep, silences)
        if ghost:
            log(f"anti-hallucination (audio) : {ghost} mots retires "
                f"(prononces 'dans' un silence detecte = impossibles).")
    dropped = mark_hallucinations(words, segments, keep, cfg)
    if dropped:
        log(f"anti-hallucination : {dropped} mots retires (faux sous-titres musique/silence).")
    retakes = remove_retakes(words, segments, keep, cfg)
    if retakes:
        log(f"prises refaites : {retakes} mots retires (on garde la derniere prise).")
    rep = collapse_repeated_phrases(words, keep, cfg)
    if rep:
        log(f"phrases repetees : {rep} mots retires (garde la derniere occurrence).")
    fs = remove_false_starts(words, keep, cfg)
    if fs:
        log(f"faux departs (phrases non finies) : {fs} mots retires (garde la reprise).")
    segs = build_segments(words, keep, cfg, silences)

    # COLD-OPEN : teaser en tete (les meilleurs instants rejoues avant l'intro, style pro).
    # config edit.cold_open = [{"start": s, "end": e}, ...] (temps ORIGINAUX).
    cold = cfg.get("edit", {}).get("cold_open") or []
    if cold:
        teaser = [{"start": round(float(c["start"]), 3), "end": round(float(c["end"]), 3)}
                  for c in cold]
        segs = teaser + segs
        log(f"cold-open : {len(teaser)} extrait(s) teaser en tete "
            f"({sum(t['end']-t['start'] for t in teaser):.1f}s).")
    emph = find_emphasis(words, keep, cfg)

    kept_dur = sum(s["end"] - s["start"] for s in segs)
    plan = {
        "keep_segments": segs,
        "emphasis": emph,
        "stats": {
            "orig_duration": round(data["duration"], 2),
            "cut_duration": round(kept_dur, 2),
            "removed_s": round(data["duration"] - kept_dur, 2),
            "n_words": len(words),
            "n_words_kept": sum(keep),
            "n_segments": len(segs),
            "n_emphasis": len(emph),
        },
    }
    save_json(os.path.join(a.work_dir, "plan.json"), plan)
    st = plan["stats"]
    log(f"plan: {st['n_segments']} segments, {st['cut_duration']}s gardees / {st['orig_duration']}s "
        f"(-{st['removed_s']}s), {st['n_emphasis']} accentuations.")


if __name__ == "__main__":
    main()
