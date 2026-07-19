"""CARTE SONORE COMPLETE : Gemini ecoute TOUT l'audio (par tranches) et decrit chaque
evenement sonore — pas seulement les paroles : impacts, cris, rires, tirs, explosions,
musiques, alarmes, silences, emotion de la voix.

Usage:
  python scripts/hear_all.py "<video>" <work_dir> [--chunk 240] [--from s --to s]

Sortie : <work_dir>/sound_map.json = liste triee d'evenements
  {"t": <s ABSOLUES>, "type": "parole|cri|rire|impact|tir|explosion|musique|alarme|ambiance",
   "quoi": "...", "interet_montage": 0-3}
+ zones: [{"start","end","ambiance","niveau_action": "calme|moyen|intense"}]
C'est le complement de dump_words.py : les mots + LA carte des sons = Claude entend tout.
Requiert GEMINI_API_KEY (.env).
"""
import argparse, json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from common import FFMPEG, run, log, die, ffprobe_info, gemini_generate


def _ts(v, default=0.0):
    """Secondes depuis ce que Gemini rend vraiment : 12.3, "12.3", "12.3s",
    "00:12.3" (MM:SS), "01:02:03" (HH:MM:SS). Piege connu : il repond en MM:SS."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().lower().replace("s", "")
    if not s:
        return default
    try:
        if ":" in s:
            parts = [float(p) for p in s.split(":")]
            sec = 0.0
            for p in parts:
                sec = sec * 60.0 + p
            return sec
        return float(s)
    except ValueError:
        m = re.search(r"\d+(?:\.\d+)?", s)
        return float(m.group()) if m else default

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("work_dir")
ap.add_argument("--chunk", type=float, default=240.0, help="taille de tranche (s)")
ap.add_argument("--from", dest="t0", type=float, default=0.0)
ap.add_argument("--to", dest="t1", type=float, default=None)
ap.add_argument("--model", default=os.environ.get("MONTEUR_GEMINI_MODEL", "gemini-2.5-flash"))
a = ap.parse_args()

info = ffprobe_info(a.video)
dur = float(info["duration"])
t1 = min(a.t1 or dur, dur)

PROMPT = (
    "Tu es l'OREILLE d'un monteur video (gameplay/vlog). Cet extrait audio couvre "
    "{start:.1f}s a {end:.1f}s de la video originale. Liste TOUS les evenements sonores "
    "notables en JSON — pas un resume, une CARTE : paroles marquantes (verbatim court), "
    "cris, rires, soupirs, tirs, explosions, impacts, klaxons, musiques (debut/fin), "
    "alarmes, sons d'interface, silences longs. Temps ABSOLUS de la video.\n"
    '{{"events": [{{"t": <s>, "type": "parole|cri|rire|impact|tir|explosion|musique|alarme|ambiance", '
    '"quoi": "description courte", "interet_montage": 0-3}}], '
    '"zones": [{{"start": <s>, "end": <s>, "ambiance": "...", "niveau_action": "calme|moyen|intense"}}]}}\n'
    "interet_montage : 3 = moment fort a garder/souligner, 0 = rien."
)

events, zones = [], []
t = a.t0
while t < t1 - 1:
    end = min(t + a.chunk, t1)
    mp3 = os.path.join(tempfile.gettempdir(), "monteur_hear.mp3")
    run([FFMPEG, "-v", "error", "-ss", str(t), "-t", str(end - t), "-i", a.video,
         "-vn", "-ac", "1", "-ar", "22050", "-b:a", "64k", "-y", mp3])
    data, last = None, None
    try:
        text = gemini_generate(
            a.model,
            lambda client: [client.files.upload(file=mp3), PROMPT.format(start=t, end=end)],
            {"response_mime_type": "application/json"})
        data = json.loads(text)
    except Exception as e:  # noqa: BLE001
        last = e
    if data is None:
        log(f"tranche {t:.0f}-{end:.0f}s : echec Gemini ({last}) — sautee")
    else:
        evs = data.get("events", []) or []
        zns = data.get("zones", []) or []
        for e in evs:
            e["t"] = _ts(e.get("t"))
        for z in zns:
            z["start"] = _ts(z.get("start"))
            z["end"] = _ts(z.get("end"))
        # garde-fou : certains modeles rendent des temps RELATIFS a la tranche
        if evs and max(e["t"] for e in evs) <= (end - t) + 2 and t > 5:
            for e in evs:
                e["t"] += t
            for z in zns:
                z["start"] += t
                z["end"] += t
        events += evs
        zones += zns
        log(f"tranche {t:.0f}-{end:.0f}s : {len(evs)} evenements")
    t = end

events.sort(key=lambda e: _ts(e.get("t")))
zones.sort(key=lambda z: _ts(z.get("start")))
out = os.path.join(a.work_dir, "sound_map.json")
json.dump({"video": a.video, "events": events, "zones": zones},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
log(f"{len(events)} evenements, {len(zones)} zones -> {out}")
forts = [e for e in events if int(e.get("interet_montage", 0)) >= 2]
for e in forts[:40]:
    print(f"{_ts(e.get('t')):7.1f}s [{e.get('type','?'):9s}] {e.get('quoi','')[:70]}")
if len(forts) > 40:
    print(f"... +{len(forts)-40} autres moments forts (voir sound_map.json)")
