"""Transcription mot-a-mot qui GARDE silences et rates (base du montage).

Etape 1 du plan theyo, les 3 outils EN PARALLELE :
  1. faster-whisper (WhisperX-style) : mots time-codes, VAD off (garde blancs/rates) ;
  2. detecteur de silence AUDIO (ffmpeg silencedetect) -> words.json["silences"] ;
  3. ElevenLabs Scribe (OPTIONNEL, si ELEVENLABS_API_KEY) : orthographe des noms
     propres fusionnee sur les timings whisper (le "anthropique -> Anthropic" du plan).

Usage: python transcribe.py <video> <work_dir> [--model large-v3] [--lang fr]
Sortie: <work_dir>/words.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request
import uuid
import glob
from common import FFMPEG, run, log, die, save_json, ffprobe_info, load_config


def add_cuda_dlls_to_path():
    """ctranslate2 (Windows) a besoin des DLL cuDNN/cuBLAS installees via pip.

    'nvidia' est un namespace package (pas de __file__) -> utiliser __path__.
    """
    added = []
    try:
        import nvidia  # noqa
        bases = list(getattr(nvidia, "__path__", []))
        for base in bases:
            for sub in ("cublas", "cudnn"):
                b = os.path.join(base, sub, "bin")
                if os.path.isdir(b):
                    try:
                        os.add_dll_directory(b)
                    except Exception:
                        pass
                    os.environ["PATH"] = b + os.pathsep + os.environ["PATH"]
                    added.append(b)
    except Exception as e:
        log(f"chargement DLL CUDA ignore: {str(e)[:120]}")
    if added:
        log(f"DLL CUDA ajoutees: {len(added)} dossier(s).")
    return added


def extract_audio(video, work_dir):
    wav = os.path.join(work_dir, "audio16k.wav")
    run([FFMPEG, "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", wav])
    return wav


def detect_silences(wav, noise_db=-35, min_s=0.25):
    """Detecteur de silence AUDIO (le 3e outil du plan theyo, en plus de whisper).

    Les gaps entre mots whisper ne suffisent pas : un rire, une respiration ou de la
    musique remplit le 'gap' sans etre un silence. silencedetect mesure l'ENERGIE reelle.
    """
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", wav,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_s}", "-f", "null", "-"],
        capture_output=True, text=True)
    silences, start = [], None
    for line in (r.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            start = float(m.group(1))
            continue
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m and start is not None:
            end = float(m.group(1))
            if end > start:
                silences.append({"start": round(start, 3), "end": round(end, 3)})
            start = None
    return silences


def _norm_token(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9%]", "", t.lower())


def scribe_words(wav, lang):
    """ElevenLabs Scribe (optionnel) : liste de mots (texte seul, ordre chronologique).

    Retourne None si pas de cle / echec (le pipeline continue en whisper seul).
    """
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    boundary = "----monteur" + uuid.uuid4().hex
    audio = open(wav, "rb").read()
    models = []
    for mid in (os.environ.get("MONTEUR_SCRIBE_MODEL", "scribe_v2"), "scribe_v1"):
        if mid not in models:
            models.append(mid)
    for model_id in models:
        parts = []
        for name, val in (("model_id", model_id), ("language_code", lang),
                          ("timestamps_granularity", "word"), ("tag_audio_events", "false")):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; "
                         f"name=\"{name}\"\r\n\r\n{val}\r\n".encode())
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                     f"filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
        body = b"".join(parts) + audio + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/speech-to-text", data=body, method="POST",
            headers={"xi-api-key": key,
                     "Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=300).read())
            toks = [w.get("text", "").strip() for w in resp.get("words", [])
                    if w.get("type", "word") == "word" and w.get("text", "").strip()]
            if toks:
                log(f"Scribe ({model_id}) : {len(toks)} mots recus.")
                return toks
        except Exception as e:
            log(f"Scribe {model_id} indisponible: {str(e)[:140]}")
    return None


def merge_scribe(words, scribe_tokens):
    """Fusion plan theyo : timings whisper (reference de coupe) + orthographe Scribe
    (meilleure sur les noms propres). L'original whisper est garde dans w_whisper."""
    import difflib
    wn = [_norm_token(w["w"]) for w in words]
    sn = [_norm_token(t) for t in scribe_tokens]
    sm = difflib.SequenceMatcher(None, wn, sn, autojunk=False)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag not in ("equal", "replace") or (i2 - i1) != (j2 - j1):
            continue
        for k in range(i2 - i1):
            w, s = words[i1 + k], scribe_tokens[j1 + k]
            # la ponctuation finale vient de whisper (elle pilote la coupe de phrases)
            trail = re.search(r"[.!?,…]+$", w["w"])
            new = s + (trail.group(0) if trail and not re.search(r"[.!?,…]$", s) else "")
            if new != w["w"]:
                w["w_whisper"] = w["w"]
                w["w"] = new
                changed += 1
    return changed


def transcribe(wav, model_name, lang, total_s=None):
    from faster_whisper import WhisperModel
    tries = [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    last = None
    for device, compute in tries:
        try:
            log(f"chargement modele {model_name} sur {device}/{compute}...")
            model = WhisperModel(model_name, device=device, compute_type=compute)
            log("transcription en cours (word timestamps, VAD pour ne decoder que la parole)...")
            # Les BLANCS ne viennent PAS d'un VAD eteint : ils sont mesures a part par
            # detect_silences() (ffmpeg silencedetect) -> words.json["silences"]. Laisser le
            # VAD OFF sur du gameplay faisait decoder le bruit du jeu : whisper part en boucle
            # de repetition puis remplit TOUT en "Sous-titres par ..." (mesure sur R.E.P.O. :
            # 30 des 37 min perdues, alors que le meme extrait isole se transcrit parfaitement).
            # condition_on_previous_text=False : empeche la contagion d'une hallucination.
            # VAD PERMISSIF (seuil 0.5 par defaut = mange les attaques de phrase quand la
            # voix est basse sous le jeu : mesure sur R.E.P.O., "Alors quelles sont les
            # nouveautes" — la 1re phrase de la video — etait perdue). On abaisse le seuil et
            # on elargit la marge : whisper ne decode toujours pas les longues zones de bruit
            # (donc pas d'hallucinations) mais ne rate plus les debuts de phrase.
            segments, info = model.transcribe(
                wav, language=lang, word_timestamps=True,
                vad_filter=True,
                vad_parameters={"threshold": 0.2, "min_silence_duration_ms": 700,
                                "speech_pad_ms": 600},
                beam_size=5, condition_on_previous_text=False,
            )
            # generateur consomme ICI, avec progression : sans ca, aucune trace pendant
            # 40 min et impossible de distinguer "ca calcule" de "c'est bloque".
            out, nxt = [], 0.0
            for s in segments:
                out.append(s)
                if s.end >= nxt:
                    pct = f" ({100.0 * s.end / total_s:.0f}%)" if total_s else ""
                    log(f"  ... {s.end / 60.0:.1f} min transcrites{pct}, {len(out)} segments")
                    nxt = s.end + 60.0
            return out, info, f"{device}/{compute}"
        except Exception as e:
            last = e
            log(f"echec {device}/{compute}: {str(e)[:180]}")
    die(f"transcription impossible. Derniere erreur: {last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("work_dir")
    ap.add_argument("--model", default=os.environ.get("MONTEUR_MODEL", "large-v3"))
    ap.add_argument("--lang", default="fr")
    a = ap.parse_args()
    os.makedirs(a.work_dir, exist_ok=True)

    add_cuda_dlls_to_path()
    info = ffprobe_info(a.video)
    if not info["has_audio"]:
        die("la video n'a pas de piste audio.")
    wav = extract_audio(a.video, a.work_dir)

    ecfg = load_config(a.work_dir).get("edit", {})
    silences = detect_silences(wav, ecfg.get("silence_noise_db", -35),
                               ecfg.get("silence_min_s", 0.25))
    log(f"detecteur de silence : {len(silences)} silences audio "
        f"({sum(s['end']-s['start'] for s in silences):.1f}s au total).")

    segments, tinfo, backend = transcribe(wav, a.model, a.lang,
                                          total_s=float(info.get("duration") or 0) or None)

    words = []
    seg_out = []
    for s in segments:
        seg_out.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        for w in (s.words or []):
            words.append({
                "w": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
                "prob": round(getattr(w, "probability", 1.0), 3),
            })

    toks = scribe_words(wav, a.lang)
    if toks:
        n = merge_scribe(words, toks)
        log(f"Scribe fusionne : {n} mots corriges (orthographe/noms propres).")

    out = {
        "video": os.path.abspath(a.video),
        "backend": backend,
        "language": getattr(tinfo, "language", a.lang),
        "duration": info["duration"],
        "fps": info["fps"],
        "width": info["width"],
        "height": info["height"],
        "words": words,
        "segments": seg_out,
        "silences": silences,
    }
    save_json(os.path.join(a.work_dir, "words.json"), out)
    log(f"OK: {len(words)} mots, {len(seg_out)} segments -> words.json (backend {backend})")


if __name__ == "__main__":
    main()
