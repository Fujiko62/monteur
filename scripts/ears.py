"""LES OREILLES du monteur : analyse OBJECTIVE de l'audio du montage livre.

Claude ne peut pas ecouter — ce script ecoute pour lui, en chiffres :
1. VOIX vs FOND : pour chaque fenetre parlee (captions.json), rapport entre l'energie
   de la voix et celle du fond sonore voisin -> liste des moments ou la voix est noyee.
2. JONCTIONS DE COUPE : re-transcrit le fichier FINAL (whisper) et verifie que les mots
   attendus autour de chaque coupe sont bien reconnus -> une coupe qui hache un mot ou
   interrompt le discours est DETECTEE, pas devinee.

Usage: python ears.py <video_finale> --work work/<nom> [--model small] [--skip-transcribe]
Sortie: work/<nom>/ears_report.json + resume lisible sur stdout.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import wave
from common import FFMPEG, run, log, die, save_json, load_json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from transcribe import add_cuda_dlls_to_path  # noqa: E402


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t.lower())


def extract_wav(video, out):
    run([FFMPEG, "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", out])
    return out


def load_rms(wav_path, hop_s=0.05):
    """Energie RMS (dBFS) par tranche de 50ms, via numpy (present avec faster-whisper)."""
    import numpy as np
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
    data /= 32768.0
    hop = int(sr * hop_s)
    n = len(data) // hop
    rms = np.sqrt((data[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    return db, hop_s


def voice_vs_bed(caps, db, hop_s):
    """Pour chaque fenetre parlee : energie pendant la parole vs fond autour (non-parle).
    Un ecart faible = la voix ne ressort pas du jeu/de la musique."""
    import numpy as np
    n = len(db)
    speech = np.zeros(n, dtype=bool)
    for c in caps:
        a, b = int(c["start"] / hop_s), int(c["end"] / hop_s) + 1
        speech[max(0, a):min(n, b)] = True
    # regroupe les mots en phrases (gap > 0.8s)
    phrases = []
    cur = None
    for c in caps:
        if cur and c["start"] - cur["end"] <= 0.8:
            cur["end"] = c["end"]
            cur["text"] += " " + c["w"]
        else:
            if cur:
                phrases.append(cur)
            cur = {"start": c["start"], "end": c["end"], "text": c["w"]}
    if cur:
        phrases.append(cur)

    out = []
    for p in phrases:
        a, b = int(p["start"] / hop_s), int(p["end"] / hop_s) + 1
        if b <= a or b > n:
            continue
        v = float(np.median(db[a:b]))
        # fond : tranches NON parlees dans les 4s autour de la phrase
        lo, hi = max(0, a - int(4 / hop_s)), min(n, b + int(4 / hop_s))
        bed_idx = [i for i in range(lo, hi) if not speech[i]]
        bed = float(np.median(db[bed_idx])) if len(bed_idx) >= 8 else None
        out.append({"start": round(p["start"], 2), "end": round(p["end"], 2),
                    "voice_db": round(v, 1),
                    "bed_db": round(bed, 1) if bed is not None else None,
                    "snr_db": round(v - bed, 1) if bed is not None else None,
                    "text": p["text"][:80]})
    return out


def junction_check(work, final_words):
    """Verifie chaque jonction de coupe : les mots attendus juste avant/apres la coupe
    sont-ils reconnus dans l'audio FINAL a ce moment-la ? Non = coupe qui hache."""
    offsets = load_json(os.path.join(work, "offsets.json"))["offsets"]
    caps = load_json(os.path.join(work, "captions.json"))
    recog = [(w["start"], w["end"], norm(w["w"])) for w in final_words if norm(w["w"])]
    issues = []
    for cut_t in offsets[1:]:  # chaque debut de segment = une jonction
        exp = [c for c in caps if abs((c["start"] + c["end"]) / 2 - cut_t) < 1.2]
        exp_tok = [norm(c["w"]) for c in exp if norm(c["w"])]
        if len(exp_tok) < 2:
            continue
        got_tok = [t for (a, b, t) in recog if abs((a + b) / 2 - cut_t) < 2.0]
        found = sum(1 for t in exp_tok if any(t == g or (len(t) > 3 and t in g) for g in got_tok))
        ratio = found / len(exp_tok)
        if ratio < 0.5:
            issues.append({"t": round(cut_t, 2), "attendu": " ".join(c["w"] for c in exp)[:70],
                           "reconnu_ratio": round(ratio, 2)})
    return issues, len(offsets) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--work", required=True)
    ap.add_argument("--model", default="small", help="modele whisper pour la verif (rapide)")
    ap.add_argument("--skip-transcribe", action="store_true",
                    help="ne refait pas la reconnaissance (garde ears_recog.json)")
    ap.add_argument("--mix-only", action="store_true",
                    help="seulement la mesure voix/fond (rapide, pas de whisper). "
                         "Imprime MEDIAN_SNR_DB=x en derniere ligne (pour run.py).")
    a = ap.parse_args()

    wav = extract_wav(a.video, os.path.join(a.work, "ears_final.wav"))
    caps = load_json(os.path.join(a.work, "captions.json"))
    db, hop = load_rms(wav)
    phrases = voice_vs_bed(caps, db, hop)
    with_snr = [p for p in phrases if p["snr_db"] is not None]
    bad = sorted([p for p in with_snr if p["snr_db"] < 4.0], key=lambda p: p["snr_db"])
    log(f"OREILLES/mix : {len(with_snr)} phrases mesurees, "
        f"{len(bad)} ou la voix ressort de moins de 4 dB du fond.")
    for p in bad[:10]:
        log(f"  VOIX NOYEE {p['start']:7.1f}s snr={p['snr_db']:+.1f}dB  \"{p['text']}\"")

    if a.mix_only:
        snrs = sorted(p["snr_db"] for p in with_snr)
        med = snrs[len(snrs) // 2] if snrs else 99.0
        save_json(os.path.join(a.work, "ears_report.json"),
                  {"phrases": phrases, "voix_noyee": bad,
                   "resume": {"phrases_mesurees": len(with_snr), "voix_noyee": len(bad),
                              "median_snr_db": med}})
        print(f"MEDIAN_SNR_DB={med}")
        return

    recog_path = os.path.join(a.work, "ears_recog.json")
    if a.skip_transcribe and os.path.exists(recog_path):
        final_words = load_json(recog_path)
    else:
        add_cuda_dlls_to_path()
        from faster_whisper import WhisperModel
        log(f"OREILLES/jonctions : re-transcription du fichier final ({a.model})...")
        try:
            model = WhisperModel(a.model, device="cuda", compute_type="float16")
        except Exception:
            model = WhisperModel(a.model, device="cpu", compute_type="int8")
        segs, _ = model.transcribe(wav, language="fr", word_timestamps=True, vad_filter=False)
        final_words = []
        for s in segs:
            for w in (s.words or []):
                final_words.append({"w": w.word.strip(), "start": round(w.start, 3),
                                    "end": round(w.end, 3)})
        save_json(recog_path, final_words)
    issues, n_junctions = junction_check(a.work, final_words)
    log(f"OREILLES/jonctions : {n_junctions} coupes verifiees, {len(issues)} suspectes "
        f"(mots attendus mal reconnus autour de la coupe).")
    for i in issues[:10]:
        log(f"  JONCTION {i['t']:7.1f}s ratio={i['reconnu_ratio']}  \"{i['attendu']}\"")

    report = {"phrases": phrases, "voix_noyee": bad, "jonctions_suspectes": issues,
              "n_jonctions": n_junctions,
              "resume": {"phrases_mesurees": len(with_snr), "voix_noyee": len(bad),
                         "jonctions_suspectes": len(issues)}}
    save_json(os.path.join(a.work, "ears_report.json"), report)
    log(f"rapport -> {os.path.join(a.work, 'ears_report.json')}")


if __name__ == "__main__":
    main()
