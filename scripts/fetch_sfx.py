"""Telecharge de VRAIS bruitages depuis des banques en ligne gratuites, puis les
nettoie automatiquement (conseil theyo : "des effets sonores parfaitement coupes
au debut et a la fin, sinon ca decale le placement sur la timeline").

Pipeline par son : telecharger -> analyser -> auto-trim des silences tete/queue ->
normaliser -> VALIDER (rejet si vide, trop long, coupe a moitie / fin brutale).

Usage:
  python fetch_sfx.py --all                    # installe le soundboard complet
  python fetch_sfx.py --url <URL> --name pop   # ajoute un son depuis une URL directe
  python fetch_sfx.py --file <chemin> --name x # importe + nettoie un fichier local
  python fetch_sfx.py --check                  # re-valide tous les sons installes
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import urllib.request
import wave
from common import FFMPEG, FFPROBE, ROOT, run, log

SFX_DIR = os.path.join(ROOT, "remotion", "public", "sfx")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Sources gratuites, libres d'usage (licence Mixkit: gratuit usage commercial,
# pas d'attribution requise). URLs directes des fichiers audio.
# IDs verifies sur mixkit.co le 2026-07-11 (titre en commentaire).
SOUNDBOARD = {
    "whoosh":     ["https://assets.mixkit.co/active_storage/sfx/1490/1490.wav",   # Fast whoosh transition
                   "https://assets.mixkit.co/active_storage/sfx/1489/1489.wav"],  # Air woosh
    "impact":     ["https://assets.mixkit.co/active_storage/sfx/2902/2902.wav",   # Movie impact intro presentation
                   "https://assets.mixkit.co/active_storage/sfx/788/788.wav"],    # Big cinematic impact
    "pop":        ["https://assets.mixkit.co/active_storage/sfx/2358/2358.wav",   # Long pop
                   "https://assets.mixkit.co/active_storage/sfx/2925/2925.wav"],  # Soap bubble sound
    "click":      ["https://assets.mixkit.co/active_storage/sfx/1109/1109.wav",   # Select click
                   "https://assets.mixkit.co/active_storage/sfx/2568/2568.wav"],  # Cool interface click tone
    "riser":      ["https://assets.mixkit.co/active_storage/sfx/1146/1146.wav",   # Intro transition
                   "https://assets.mixkit.co/active_storage/sfx/2290/2290.wav"],  # Epic orchestra transition
    "ding":       ["https://assets.mixkit.co/active_storage/sfx/2357/2357.wav",   # Bubble pop up alert notification
                   "https://assets.mixkit.co/active_storage/sfx/2356/2356.wav"],  # Dry pop up notification alert
    "boom":       ["https://assets.mixkit.co/active_storage/sfx/2782/2782.wav",   # Epic impact afar explosion
                   "https://assets.mixkit.co/active_storage/sfx/2804/2804.wav"],  # Bomb drop impact
    "transition": ["https://assets.mixkit.co/active_storage/sfx/166/166.wav",     # Fast small sweep transition
                   "https://assets.mixkit.co/active_storage/sfx/1465/1465.wav"],  # Vacuum swoosh transition
    "notif":      ["https://assets.mixkit.co/active_storage/sfx/2354/2354.wav",   # Message pop alert
                   "https://assets.mixkit.co/active_storage/sfx/211/211.wav"],    # Retro arcade casino notification
    "subscribe":  ["https://assets.mixkit.co/active_storage/sfx/211/211.wav",     # Retro arcade casino notification
                   "https://assets.mixkit.co/active_storage/sfx/2357/2357.wav"],  # Bubble pop up alert
}

# Pack VARIATION : plusieurs variantes par categorie pour ne JAMAIS repeter le meme son.
# IDs verifies sur mixkit.co (titres en commentaire).
VARIETY_PACK = {
    "whoosh2":     ["https://assets.mixkit.co/active_storage/sfx/1489/1489.wav"],   # Air woosh
    "whoosh3":     ["https://assets.mixkit.co/active_storage/sfx/1486/1486.wav"],   # Tunnel reverb woosh
    "swoosh_soft": ["https://assets.mixkit.co/active_storage/sfx/1474/1474.wav"],   # Windy swoosh
    "transition2": ["https://assets.mixkit.co/active_storage/sfx/1465/1465.wav"],   # Vacuum swoosh
    "transition3": ["https://assets.mixkit.co/active_storage/sfx/3120/3120.wav"],   # Technology slide
    "impact2":     ["https://assets.mixkit.co/active_storage/sfx/788/788.wav"],     # Big cinematic impact
    "impact3":     ["https://assets.mixkit.co/active_storage/sfx/2150/2150.wav"],   # Impact of a blow
    "pop2":        ["https://assets.mixkit.co/active_storage/sfx/2925/2925.wav"],   # Soap bubble
    "pop3":        ["https://assets.mixkit.co/active_storage/sfx/2359/2359.wav"],   # Silly pop cluster
    "click2":      ["https://assets.mixkit.co/active_storage/sfx/275/275.wav"],     # Double click
    "ding2":       ["https://assets.mixkit.co/active_storage/sfx/2356/2356.wav"],   # Dry pop up alert
    "boom2":       ["https://assets.mixkit.co/active_storage/sfx/2804/2804.wav"],   # Bomb drop impact
    "shutter":     ["https://assets.mixkit.co/active_storage/sfx/1133/1133.wav"],   # Camera shutter
}

# Pack "fun / meme" (myinstants, sons de meme populaires) pour vidéos non-serieuses.
FUN_PACK = {
    "vine_boom":      ["https://www.myinstants.com/media/sounds/vine-boom.mp3"],
    "record_scratch": ["https://www.myinstants.com/media/sounds/record-scratch.mp3",
                       "https://www.myinstants.com/media/sounds/record-scratch-clean.mp3"],
    "bruh":           ["https://www.myinstants.com/media/sounds/bruh-sound-effect_WstdzdM.mp3"],
    "sad_trombone":   ["https://www.myinstants.com/media/sounds/sad-trombone.mp3",
                       "https://www.myinstants.com/media/sounds/sadtrombone.swf.mp3"],
    "airhorn":        ["https://www.myinstants.com/media/sounds/mlg-airhorn.mp3",
                       "https://www.myinstants.com/media/sounds/air-horn_1.mp3"],
}

MAX_DUR = {"riser": 3.5, "transition": 2.5, "boom": 2.5,
           "sad_trombone": 3.0, "airhorn": 2.5, "vine_boom": 2.0, "record_scratch": 2.5}
DEFAULT_MAX_DUR = 2.0


def download(url, dst):
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=45).read()
    if len(data) < 1000:
        raise ValueError(f"fichier trop petit ({len(data)} octets)")
    open(dst, "wb").write(data)


def probe_audio(path):
    r = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_streams",
             "-show_format", path])
    d = json.loads(r.stdout)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if not a:
        raise ValueError("pas de flux audio")
    return float(d["format"].get("duration") or 0)


def analyze_wav(path):
    """Retourne (dur, rms_par_tranche_20ms) sur un wav mono 48k s16le."""
    with wave.open(path, "rb") as w:
        n, sr = w.getnframes(), w.getframerate()
        raw = w.readframes(n)
    samples = struct.unpack(f"<{len(raw)//2}h", raw)
    dur = n / sr
    win = max(1, int(sr * 0.02))
    rms = []
    for i in range(0, len(samples), win):
        chunk = samples[i:i + win]
        if chunk:
            rms.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)) / 32768.0)
    return dur, rms


def db(x):
    return 20 * math.log10(max(x, 1e-9))


def clean_and_validate(src, name):
    """Trim silences tete/queue, normalise, valide. Retourne (ok, raison)."""
    max_dur = MAX_DUR.get(name, DEFAULT_MAX_DUR)
    mono = src + ".mono.wav"
    # decode -> mono 48k pour analyse
    run([FFMPEG, "-y", "-i", src, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", mono])
    dur, rms = analyze_wav(mono)
    if not rms or max(rms) < 0.005:
        os.remove(mono)
        return False, "quasi silencieux"

    # seuil relatif : -35 dB sous le pic (plancher a -55 dBFS)
    peak = max(rms)
    thr = max(peak * (10 ** (-35 / 20)), 10 ** (-55 / 20))
    first = next((i for i, v in enumerate(rms) if v >= thr), None)
    last = next((i for i in range(len(rms) - 1, -1, -1) if rms[i] >= thr), None)
    os.remove(mono)
    if first is None:
        return False, "aucun contenu au-dessus du seuil"
    t0 = first * 0.02
    t1 = (last + 1) * 0.02
    trimmed_dur = t1 - t0
    if trimmed_dur < 0.03:
        return False, f"trop court apres trim ({trimmed_dur:.2f}s)"
    if trimmed_dur > max_dur:
        # trop long -> on garde le debut (l'attaque) et on fade la fin
        t1 = t0 + max_dur

    # detection "coupe a moitie" : la fin doit retomber (fin < 60% du pic),
    # sinon on repare avec un fade-out au lieu de rejeter.
    end_idx = min(int(t1 / 0.02), len(rms)) - 1
    tail = rms[max(0, end_idx - 3):end_idx + 1]
    abrupt = tail and (sum(tail) / len(tail)) > 0.6 * peak
    fade_d = 0.12 if abrupt else 0.03

    out = os.path.join(SFX_DIR, f"{name}.wav")
    dur_final = t1 - t0
    af = (f"atrim=start={t0:.3f}:end={t1:.3f},asetpts=PTS-STARTPTS,"
          f"afade=t=in:st=0:d=0.008,"
          f"afade=t=out:st={max(0.0, dur_final - fade_d):.3f}:d={fade_d:.3f},"
          f"loudnorm=I=-14:TP=-1.0:LRA=9")
    run([FFMPEG, "-y", "-i", src, "-af", af, "-ac", "2", "-ar", "48000",
         "-c:a", "pcm_s16le", out])
    note = " (fin brutale reparee au fade)" if abrupt else ""
    return True, f"{dur_final:.2f}s, trim tete {t0:.2f}s{note}"


def search_mixkit(query, n=6):
    """Cherche sur mixkit.co et retourne [(titre, url_wav)] (parse HTML, sans cle)."""
    import urllib.parse
    q = urllib.parse.quote(query)
    urls = [f"https://mixkit.co/free-sound-effects/search/?q={q}",
            f"https://mixkit.co/free-sound-effects/{query.strip().lower().replace(' ', '-')}/"]
    out, seen = [], set()
    for u in urls:
        try:
            req = urllib.request.Request(u, headers=UA)
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception:
            continue
        import re as _re
        for m in _re.finditer(r"/active_storage/sfx/(\d+)/", html):
            i = m.group(1)
            if i not in seen:
                seen.add(i)
                out.append((f"mixkit-{i}", f"https://assets.mixkit.co/active_storage/sfx/{i}/{i}.wav"))
            if len(out) >= n:
                return out
        if out:
            break
    return out


def search_myinstants(query, n=6):
    """Cherche sur myinstants.com (sons de meme) et retourne [(titre, url_mp3)]."""
    import urllib.parse
    import re as _re
    q = urllib.parse.quote_plus(query)
    try:
        req = urllib.request.Request(f"https://www.myinstants.com/en/search/?name={q}", headers=UA)
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        return []
    out, seen = [], set()
    for m in _re.finditer(r"play\('(/media/sounds/[^']+\.mp3)'", html):
        p = m.group(1)
        if p not in seen:
            seen.add(p)
            out.append((os.path.basename(p)[:40], "https://www.myinstants.com" + p))
        if len(out) >= n:
            break
    return out


def _bank_hashes(exclude_name):
    """Empreintes MD5 des sons deja en banque (pour rejeter les doublons deguises :
    la recherche Mixkit peut piegier avec un son 'populaire' present sur toutes les pages)."""
    import hashlib
    hashes = {}
    for f in os.listdir(SFX_DIR):
        if f.endswith(".wav") and f[:-4] != exclude_name:
            try:
                hashes[hashlib.md5(open(os.path.join(SFX_DIR, f), "rb").read()).hexdigest()] = f
            except OSError:
                pass
    return hashes


def search_and_install(query, name, source="auto"):
    """Cherche le son sur internet, telecharge le premier candidat VALIDE (filtre qualite
    + anti-doublon : un candidat identique a un son deja en banque est rejete)."""
    cands = []
    if source in ("auto", "mixkit"):
        cands += search_mixkit(query)
    if source in ("auto", "myinstants"):
        cands += search_myinstants(query)
    if not cands:
        log(f"aucun resultat pour '{query}'.")
        return False
    log(f"{len(cands)} candidats pour '{query}'.")
    import hashlib
    bank = _bank_hashes(name)
    tmp = os.path.join(SFX_DIR, f"_{name}.dl")
    for title, url in cands:
        try:
            download(url, tmp)
            probe_audio(tmp)
            ok, why = clean_and_validate(tmp, name)
            if ok:
                out = os.path.join(SFX_DIR, f"{name}.wav")
                h = hashlib.md5(open(out, "rb").read()).hexdigest()
                if h in bank:
                    log(f"{name}: candidat '{title}' = DOUBLON de {bank[h]} -> rejete.")
                    os.remove(out)
                    continue
                log(f"{name}: OK depuis '{title}' [{why}]")
                os.remove(tmp)
                return True
            log(f"{name}: candidat '{title}' rejete ({why}).")
        except Exception as e:
            log(f"{name}: echec '{title}': {str(e)[:80]}")
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def install_one(name, urls):
    tmp = os.path.join(SFX_DIR, f"_{name}.dl")
    for url in urls:
        try:
            log(f"{name}: telechargement {url.split('/')[-1]}...")
            download(url, tmp)
            probe_audio(tmp)  # verifie que c'est bien de l'audio decodable
            ok, why = clean_and_validate(tmp, name)
            if ok:
                log(f"{name}: OK [{why}]")
                os.remove(tmp)
                return True
            log(f"{name}: REJETE ({why}), source suivante...")
        except Exception as e:
            log(f"{name}: echec {str(e)[:100]}, source suivante...")
    if os.path.exists(tmp):
        os.remove(tmp)
    log(f"{name}: AUCUNE source valide -> l'ancien fichier est conserve.")
    return False


def check_all():
    bad = []
    for f in sorted(os.listdir(SFX_DIR)):
        if not f.endswith(".wav"):
            continue
        p = os.path.join(SFX_DIR, f)
        mono = p + ".chk.wav"
        run([FFMPEG, "-y", "-i", p, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", mono])
        dur, rms = analyze_wav(mono)
        os.remove(mono)
        peak = max(rms) if rms else 0
        head = rms[:5]
        head_silent = head and max(head) < peak * 0.05
        status = []
        if peak < 0.005:
            status.append("SILENCIEUX")
        if head_silent:
            status.append("SILENCE EN TETE")
        if dur > 4:
            status.append(f"TROP LONG {dur:.1f}s")
        verdict = ", ".join(status) if status else "ok"
        log(f"{f}: {dur:.2f}s, pic {db(peak):.0f} dBFS -> {verdict}")
        if status:
            bad.append(f)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fun", action="store_true", help="pack meme/fun (myinstants)")
    ap.add_argument("--variety", action="store_true", help="pack variation (13 sons de plus)")
    ap.add_argument("--search", help="cherche un son sur internet (mixkit+myinstants)")
    ap.add_argument("--source", default="auto", choices=["auto", "mixkit", "myinstants"])
    ap.add_argument("--url")
    ap.add_argument("--file")
    ap.add_argument("--name")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    os.makedirs(SFX_DIR, exist_ok=True)

    if a.check:
        bad = check_all()
        sys.exit(1 if bad else 0)
    if a.search:
        if not a.name:
            die_msg = "il faut --name avec --search"
            log(die_msg)
            sys.exit(1)
        ok = search_and_install(a.search, a.name, a.source)
        if ok:
            print(f"{a.name}.wav")
        sys.exit(0 if ok else 2)
    if a.all or a.fun or a.variety:
        board = {}
        if a.all:
            board.update(SOUNDBOARD)
            board.update(VARIETY_PACK)
            board.update(FUN_PACK)
        if a.fun:
            board.update(FUN_PACK)
        if a.variety:
            board.update(VARIETY_PACK)
        results = {n: install_one(n, urls) for n, urls in board.items()}
        ok = sum(results.values())
        log(f"== soundboard: {ok}/{len(results)} sons installes depuis internet ==")
        return
    if a.url and a.name:
        tmp = os.path.join(SFX_DIR, f"_{a.name}.dl")
        download(a.url, tmp)
        probe_audio(tmp)
        ok, why = clean_and_validate(tmp, a.name)
        os.remove(tmp)
        log(f"{a.name}: {'OK' if ok else 'REJETE'} [{why}]")
        return
    if a.file and a.name:
        ok, why = clean_and_validate(a.file, a.name)
        log(f"{a.name}: {'OK' if ok else 'REJETE'} [{why}]")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
