"""LES OREILLES A LA DEMANDE : Gemini ECOUTE un passage audio et raconte ce qu'il entend.

Usage:
  python scripts/listen.py "<video>" <start> <end>
  python scripts/listen.py "C:/Videos/rush.mkv" 280 310

Sort un JSON : ce qui est dit, les sons du jeu/ambiance, les reactions, l'emotion,
les moments forts timestampes (temps ABSOLUS de la video, pas relatifs a l'extrait).
Requiert GEMINI_API_KEY (.env). GEMINI_API_KEY_2 (autre compte) = bascule auto si quota.
"""
import argparse, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, run, die, gemini_generate

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("start", type=float)
ap.add_argument("end", type=float)
ap.add_argument("--model", default=os.environ.get("MONTEUR_GEMINI_MODEL", "gemini-2.5-flash"))
a = ap.parse_args()

wav = os.path.join(tempfile.gettempdir(), "monteur_listen.mp3")
run([FFMPEG, "-v", "error", "-ss", str(a.start), "-t", str(a.end - a.start), "-i", a.video,
     "-vn", "-ac", "1", "-ar", "22050", "-b:a", "64k", "-y", wav])

prompt = (
    f"Tu es l'oreille d'un monteur video. Cet extrait audio couvre {a.start:.1f}s a {a.end:.1f}s "
    f"de la video originale. Decris PRECISEMENT ce que tu entends, en JSON:\n"
    '{"paroles": "ce qui est dit (verbatim si possible)", '
    '"sons_jeu": "sons de jeu/ambiance entendus", '
    '"emotion": "ton de la voix (excite/frustre/calme/mort de rire...)", '
    '"moments_forts": [{"t": <secondes ABSOLUES video>, "quoi": "cri/rire/impact/klaxon..."}], '
    '"conseil_montage": "ou couper / quoi souligner"}'
)

try:
    text = gemini_generate(
        a.model,
        lambda client: [client.files.upload(file=wav), prompt],
        {"response_mime_type": "application/json"})
    print(json.dumps(json.loads(text), ensure_ascii=False, indent=1))
except Exception as e:  # noqa: BLE001
    die(f"Gemini listen: {e}")
