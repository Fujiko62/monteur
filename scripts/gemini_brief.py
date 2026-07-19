"""BRIEF Gemini AVANT montage : Gemini regarde la video BRUTE et briefe le monteur
(vision globale que Claude n'a pas). A lancer juste apres la transcription.

Sortie : <work_dir>/brief.json — resume, ton, moments cles timestampes (fail/hype/
explication/punchline), suggestions d'animations/b-roll, meilleurs shorts, defauts image.

Requiert GEMINI_API_KEY (.env). Gros fichier : un proxy 720p est cree automatiquement.
Usage: python gemini_brief.py <video> <work_dir> [--model gemini-2.5-flash]
"""
import argparse
import json
import os
import re
import sys
import time
from common import FFMPEG, run, log, die, save_json, load_dotenv, make_proxy as _shared_proxy

load_dotenv()

PROMPT = """Tu es un CHEF MONTEUR senior. Regarde toute la video (brute, non montee) et
briefe ton monteur. Reponds UNIQUEMENT en JSON valide, cles :
- "resume": 2 phrases (de quoi parle la video, qui parle, contexte visuel).
- "ton": "fun" ou "pro" (fun = gameplay/vlog/leger ; pro = presentation/explication).
- "moments_cles": liste [{"t": secondes, "type": "fail|hype|punchline|explication|moment_visuel",
   "description": "...", "suggestion": "quoi faire au montage a ce moment"}] (10-20 max, les
   MEILLEURS moments, timestamps precis).
- "animations_suggerees": liste [{"t": secondes, "type": "stat|bars|calendar|diagram|image|callout",
   "detail": "..."}] uniquement la ou ca ILLUSTRE vraiment le propos.
- "meilleurs_shorts": liste [{"start": s, "end": s, "hook": "texte d'accroche court",
   "raison": "..."}] 2-3 extraits AUTONOMES (comprehensibles seuls, avec le contexte complet,
   debut et fin de phrase naturels, 20-50s).
- "defauts_image": problemes visuels a corriger (sombre, flou, cadrage...).
- "musique": ambiance conseillee (upbeat/chill/epic/corporate/hiphop/tension/happy) ou "aucune".
Sois PRECIS sur les timestamps. Pas de politesse, pas de texte hors JSON."""


def make_proxy(video, work_dir):
    return _shared_proxy(video, work_dir, name="proxy_brief.mp4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("work_dir")
    ap.add_argument("--model", default=os.environ.get("MONTEUR_GEMINI_MODEL", "gemini-2.5-flash"))
    a = ap.parse_args()
    from common import gemini_keys, is_quota_error
    keys = gemini_keys()
    if not keys:
        log("GEMINI_API_KEY absent : brief saute (le monteur travaillera sans les yeux).")
        sys.exit(2)
    try:
        from google import genai
    except Exception:
        log("pip install google-genai")
        sys.exit(2)

    os.makedirs(a.work_dir, exist_ok=True)
    up = make_proxy(a.video, a.work_dir)
    log(f"[gemini] upload {os.path.basename(up)}...")

    brief = None
    last = ""
    for ki, key in enumerate(keys, 1):
        client = genai.Client(api_key=key)
        f = client.files.upload(file=up)
        while getattr(f, "state", None) and str(f.state.name) == "PROCESSING":
            time.sleep(3)
            f = client.files.get(name=f.name)
        log("[gemini] analyse globale de la video...")
        quota_hit = False
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=a.model, contents=[f, PROMPT],
                    config={"response_mime_type": "application/json"},  # JSON force
                )
                txt = resp.text or ""
                last = txt
                m = re.search(r"\{.*\}", txt, re.S)
                if m:
                    brief = json.loads(m.group(0))
                    break
                log(f"tentative {attempt+1}: reponse vide/non-JSON, retry...")
            except Exception as e:
                last = str(e)
                if is_quota_error(e):
                    log(f"cle Gemini #{ki} a quota -> cle suivante")
                    quota_hit = True
                    break
                log(f"tentative {attempt+1}: {str(e)[:120]}, retry...")
            time.sleep(4)
        if brief is not None or not quota_hit:
            break
    if brief is None:
        die(f"reponse Gemini inexploitable apres essais sur {len(keys)} cle(s):\n{last[:400]}")
    save_json(os.path.join(a.work_dir, "brief.json"), brief)
    log(f"OK: brief.json — ton={brief.get('ton')}, {len(brief.get('moments_cles', []))} moments, "
        f"{len(brief.get('meilleurs_shorts', []))} shorts proposes, musique={brief.get('musique')}")


if __name__ == "__main__":
    main()
