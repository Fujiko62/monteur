"""Feedback GLOBAL du rendu par Gemini (les yeux, ROLE PREPONDERANT ET DECISIONNEL).

Le plan theyo : "Gemini a cette capacite decisionnelle sur les autres modeles" — ce script
REND le verdict executoire : exit 0 si note >= seuil (livrable), exit 3 sinon (corrections
OBLIGATOIRES avant livraison, interdit de "continuer dans sa direction quand meme").

- Gros fichier : proxy 720p crf30 automatique (jamais le master — erreur connue #7).
- JSON force + 3 retries (erreur connue #16).
- Persistance : --work <dir> => append dans <dir>/review_history.json (note v1 ->
  corrections -> note v2 : la boucle laisse une trace pour DECISIONS.md).

Usage: python gemini_review.py <video|image> [--thumb] [--work work/<nom>]
       [--min-note 7] [--model gemini-2.5-flash]
Exit: 0 = valide | 2 = pas de cle/lib (review sautee) | 3 = NOTE SOUS LE SEUIL.
"""
import argparse
import json
import os
import re
import sys
import time
from common import log, load_dotenv, load_json, save_json, load_config, make_proxy

load_dotenv()


PROMPT = (
    "Tu es un monteur video pro et exigeant. Analyse cette video montee. "
    "Donne un feedback ACTIONNABLE et concis en JSON avec les cles: "
    "note_sur_10, sous_titres (lisibilite, timing, placement), coupe (cuts a cote de la plaque ?), "
    "zooms (pertinents ? trop/pas assez ?), lumiere_couleur, bruitages (trop fort/mal places ?), "
    "musique (volume vs voix ? ducking correct ? ambiance adaptee ? 'aucune' si pas de musique), "
    "rythme, problemes (liste priorisee), corrections (liste d'actions concretes). "
    "Sois direct, pas de politesse."
)

THUMB_PROMPT = (
    "Tu es un expert en miniatures YouTube (CTR). Juge cette MINIATURE. Reponds en JSON: "
    "note_sur_10, lisibilite_titre (taille, contraste, lisible sur mobile en tout petit ?), "
    "image (expressive ? sujet clair ? attire l'oeil ?), composition (titre ne cache pas le "
    "sujet ? equilibre ?), couleurs, promesse (donne envie de cliquer ? claire ?), "
    "problemes (liste), corrections (actions concretes). Sois direct."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="video OU image (--thumb)")
    ap.add_argument("--thumb", action="store_true", help="juger une MINIATURE (image)")
    ap.add_argument("--work", default=None,
                    help="dossier work : persiste le verdict dans review_history.json")
    ap.add_argument("--min-note", type=float, default=None,
                    help="seuil de validation (defaut: config review.min_note, sinon 7)")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    cfg = load_config(a.work).get("review", {})
    model = (a.model or os.environ.get("MONTEUR_GEMINI_MODEL")
             or cfg.get("gemini_model", "gemini-2.5-flash"))
    min_note = a.min_note if a.min_note is not None else float(cfg.get("min_note", 7))
    from common import gemini_keys, is_quota_error
    keys = gemini_keys()
    if not keys:
        print("GEMINI_API_KEY non defini : review Gemini ignoree.", file=sys.stderr)
        sys.exit(2)
    try:
        from google import genai
    except Exception:
        print("Installe: pip install google-genai", file=sys.stderr)
        sys.exit(2)

    up = a.video
    if not a.thumb:  # video : proxy si master lourd (image = upload direct)
        up = make_proxy(a.video, a.work or os.path.dirname(os.path.abspath(a.video)))

    prompt = THUMB_PROMPT if a.thumb else PROMPT
    print(f"[gemini] upload {os.path.basename(up)}...", file=sys.stderr)

    verdict, last = None, ""
    for ki, key in enumerate(keys, 1):
        client = genai.Client(api_key=key)
        f = client.files.upload(file=up)
        while getattr(f, "state", None) and str(f.state.name) == "PROCESSING":
            time.sleep(2)
            f = client.files.get(name=f.name)
        quota_hit = False
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model, contents=[f, prompt],
                    config={"response_mime_type": "application/json"},
                )
                txt = resp.text or ""
                last = txt
                m = re.search(r"\{.*\}", txt, re.S)
                if m:
                    verdict = json.loads(m.group(0))
                    break
                print(f"[gemini] tentative {attempt+1}: reponse vide/non-JSON, retry...",
                      file=sys.stderr)
            except Exception as e:
                last = str(e)
                if is_quota_error(e):
                    print(f"[gemini] cle #{ki} a quota -> cle suivante", file=sys.stderr)
                    quota_hit = True
                    break
                print(f"[gemini] tentative {attempt+1}: {str(e)[:120]}, retry...", file=sys.stderr)
            time.sleep(4)
        if verdict is not None or not quota_hit:
            break
    if verdict is None:
        print(f"reponse Gemini inexploitable apres essais sur {len(keys)} cle(s):\n{last[:400]}",
              file=sys.stderr)
        sys.exit(2)

    print(json.dumps(verdict, ensure_ascii=False, indent=1))

    note = None
    try:
        note = float(verdict.get("note_sur_10"))
    except (TypeError, ValueError):
        pass

    if a.work:
        hist_path = os.path.join(a.work, "review_history.json")
        hist = load_json(hist_path) if os.path.exists(hist_path) else []
        hist.append({"iteration": len(hist) + 1, "target": os.path.basename(a.video),
                     "thumb": a.thumb, "note": note, "verdict": verdict})
        save_json(hist_path, hist)
        log(f"verdict persiste -> review_history.json (iteration {len(hist)}).")

    if note is not None and note < min_note:
        log(f"VERDICT GEMINI: {note:g}/10 < seuil {min_note:g} -> NON LIVRABLE. "
            f"Le feedback est un ORDRE : appliquer les corrections puis re-juger.")
        sys.exit(3)
    if note is not None:
        log(f"VERDICT GEMINI: {note:g}/10 (seuil {min_note:g}) -> VALIDE.")


if __name__ == "__main__":
    main()
