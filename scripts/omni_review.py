"""JUGE #2 : Qwen-Omni (Alibaba Model Studio) — voit la video AVEC l'audio, comme Gemini.
Gratuit : ~1M tokens/modele pendant 90 jours (endpoint Singapour). Limite dure du modele :
150 s de video par appel -> la video est decoupee en tranches, un verdict par tranche,
puis un verdict GLOBAL agrege.

Usage:
  python scripts/omni_review.py "<video>.mp4" [--work work/<nom>] [--chunk 140]

Requiert DASHSCOPE_API_KEY dans .env (cle Model Studio, region Singapour).
Sortie : JSON global {note_sur_10, problemes, corrections, tranches:[...]} — meme esprit
que gemini_review ; s'ajoute a review_history.json si --work.
"""
import argparse, base64, json, os, sys, tempfile, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, run, log, die, ffprobe_info

ENDPOINT = os.environ.get(
    "DASHSCOPE_ENDPOINT",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")
MODEL = os.environ.get("MONTEUR_OMNI_MODEL", "qwen3-omni-flash")

PROMPT = (
    "Tu es un JUGE de montage video YouTube exigeant (gameplay/vlog, francais). Cette "
    "tranche couvre {start:.0f}s a {end:.0f}s du montage. Tu VOIS les images ET tu ENTENDS "
    "l'audio. Evalue : coupes (fluides ? phrases completes ?), texte a l'ecran (lisible, "
    "bien place, ne masque rien ?), bruitages/musique (volume vs voix, pertinence), rythme, "
    "moments morts ou ecrans de chargement restants (defaut grave). Reponds UNIQUEMENT en "
    'JSON : {{"note_sur_10": <int>, "problemes": ["defaut concret + timecode"], '
    '"corrections": ["action concrete de montage"]}}'
)


def call_omni(key, video_b64, prompt):
    body = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "video_url",
                 "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "modalities": ["text"],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return out["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--work", default=None)
    ap.add_argument("--chunk", type=float, default=140.0, help="taille de tranche (max 150 s)")
    ap.add_argument("--max-chunks", type=int, default=6,
                    help="tranches jugees max (reparties sur toute la video)")
    a = ap.parse_args()

    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        die("DASHSCOPE_API_KEY manquant (.env) — cle Alibaba Model Studio (Singapour).")

    dur = float(ffprobe_info(a.video)["duration"])
    n_total = max(1, int(dur // a.chunk) + (1 if dur % a.chunk > 5 else 0))
    # si la video est longue, on echantillonne max-chunks tranches reparties
    idxs = list(range(n_total)) if n_total <= a.max_chunks else \
        sorted({round(i * (n_total - 1) / (a.max_chunks - 1)) for i in range(a.max_chunks)})

    tranches = []
    for i in idxs:
        t0 = i * a.chunk
        t1 = min(t0 + a.chunk, dur)
        clip = os.path.join(tempfile.gettempdir(), "monteur_omni.mp4")
        # compression forte : 360p + audio mono 48k -> base64 raisonnable pour l'API
        run([FFMPEG, "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", a.video,
             "-vf", "scale=-2:360,fps=8", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "32", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "48k", "-ac", "1", "-movflags", "+faststart",
             "-y", clip])
        size_mb = os.path.getsize(clip) / 1e6
        log(f"tranche {t0:.0f}-{t1:.0f}s ({size_mb:.1f} Mo) -> Qwen-Omni...")
        b64 = base64.b64encode(open(clip, "rb").read()).decode()
        verdict, last = None, None
        for _ in range(3):
            try:
                verdict = json.loads(call_omni(key, b64, PROMPT.format(start=t0, end=t1)))
                break
            except Exception as e:  # noqa: BLE001
                last = e
        if verdict is None:
            log(f"tranche {t0:.0f}s : echec ({str(last)[:120]}) — sautee")
            continue
        verdict["start"], verdict["end"] = t0, t1
        tranches.append(verdict)
        log(f"  note tranche: {verdict.get('note_sur_10')}/10")

    if not tranches:
        die("aucune tranche jugee (cle invalide ? quota ? reseau ?)")

    notes = [t.get("note_sur_10") for t in tranches if isinstance(t.get("note_sur_10"), (int, float))]
    global_verdict = {
        "juge": f"qwen-omni/{MODEL}",
        "note_sur_10": round(sum(notes) / len(notes), 1) if notes else None,
        "problemes": [p for t in tranches for p in t.get("problemes", [])],
        "corrections": [c for t in tranches for c in t.get("corrections", [])],
        "tranches": tranches,
    }
    print(json.dumps(global_verdict, ensure_ascii=False, indent=1))
    if a.work:
        hist = os.path.join(a.work, "review_history.json")
        h = json.load(open(hist, encoding="utf-8")) if os.path.exists(hist) else []
        h.append({"juge": global_verdict["juge"], "note": global_verdict["note_sur_10"],
                  "verdict": global_verdict})
        json.dump(h, open(hist, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"VERDICT QWEN-OMNI: {global_verdict['note_sur_10']}/10 "
        f"({len(tranches)} tranche(s) vues+entendues)")


if __name__ == "__main__":
    main()
