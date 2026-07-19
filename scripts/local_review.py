"""LES YEUX LOCAUX (gratuits, illimites) : Qwen2.5-VL via Ollama juge le montage
sur des planches de frames — meme role que gemini_review, zero cle, zero quota.
C'est le SECOURS automatique quand toutes les cles Gemini sont a plat, ou un juge
d'appoint a volonte (il ne voit pas la video ENTIERE : des frames echantillonnees).

Usage:
  python scripts/local_review.py "<video>.mp4" [--frames 12] [--work work/<nom>]
  python scripts/local_review.py "<image>.png" --thumb          # juge une miniature

Requiert : Ollama (localhost:11434) + `ollama pull qwen2.5vl:7b`.
Sortie : JSON verdict (note_sur_10, problemes, corrections) — meme esprit que Gemini.
"""
import argparse, base64, json, os, subprocess, sys, tempfile, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, log, die, ffprobe_info

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MONTEUR_LOCAL_VLM", "qwen2.5vl:7b")

PROMPT_VIDEO = (
    "Tu es un JUGE de montage video exigeant (gameplay/vlog YouTube). Ces images sont des "
    "frames echantillonnees chronologiquement d'un montage. Evalue ce que tu VOIS : "
    "lisibilite des textes/callouts a l'ecran, placement (rien ne doit masquer l'action ou "
    "l'interface), coherence visuelle (une seule direction artistique), presence d'ecrans "
    "de chargement ou de frames noires (defaut grave), pertinence des effets. "
    "Reponds UNIQUEMENT en JSON : "
    '{"note_sur_10": <int>, "points_forts": ["..."], '
    '"problemes": ["defaut concret + numero de frame"], '
    '"corrections": ["action concrete de montage"]}'
)

PROMPT_THUMB = (
    "Tu es un JUGE de miniatures YouTube. Evalue cette miniature : lisibilite du titre "
    "en tout petit (mobile), contraste, emotion/sujet clair, promesse comprehensible en "
    "1 seconde. Reponds UNIQUEMENT en JSON : "
    '{"note_sur_10": <int>, "problemes": ["..."], "corrections": ["..."]}'
)


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def ollama_chat(prompt, images_b64):
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps({
            "model": MODEL, "stream": False, "format": "json",
            "messages": [{"role": "user", "content": prompt, "images": images_b64}],
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--thumb", action="store_true")
    ap.add_argument("--work", default=None)
    a = ap.parse_args()

    # Ollama joignable ?
    try:
        urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5)
    except Exception:
        # tente de demarrer le serveur (installe mais pas lance)
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            import time
            time.sleep(4)
            urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5)
        except Exception:
            die("Ollama injoignable (installe-le puis: ollama pull qwen2.5vl:7b)")

    if a.thumb:
        log(f"[local:{MODEL}] jugement miniature...")
        txt = ollama_chat(PROMPT_THUMB, [b64(a.media)])
    else:
        dur = float(ffprobe_info(a.media)["duration"])
        tmp = tempfile.mkdtemp(prefix="monteur_localrev_")
        imgs = []
        n = max(4, a.frames)
        for i in range(n):
            t = dur * (i + 0.5) / n
            f = os.path.join(tmp, f"f{i:02d}.jpg")
            subprocess.run([FFMPEG, "-v", "error", "-ss", str(t), "-i", a.media,
                            "-frames:v", "1", "-q:v", "6",
                            "-vf", "scale=768:-2,format=yuvj420p", "-strict", "unofficial",
                            "-y", f], check=True)
            imgs.append(b64(f))
        log(f"[local:{MODEL}] jugement sur {n} frames ({dur:.0f}s de video)...")
        txt = ollama_chat(PROMPT_VIDEO, imgs)

    try:
        verdict = json.loads(txt)
    except json.JSONDecodeError:
        die(f"reponse locale non-JSON: {txt[:300]}")
    print(json.dumps(verdict, ensure_ascii=False, indent=1))
    note = verdict.get("note_sur_10")
    if a.work and note is not None:
        hist = os.path.join(a.work, "review_history.json")
        h = json.load(open(hist, encoding="utf-8")) if os.path.exists(hist) else []
        h.append({"juge": f"local/{MODEL}", "note": note, "verdict": verdict})
        json.dump(h, open(hist, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"VERDICT LOCAL ({MODEL}): {note}/10")


if __name__ == "__main__":
    main()
