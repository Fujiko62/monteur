"""Musique de fond A LA DEMANDE (rien de pre-telecharge) : telecharge UNIQUEMENT le morceau
necessaire selon l'ambiance, dans remotion/public/music/. Source fiable : Mixkit (libre,
usage commercial, sans attribution).

Usage:
  python fetch_music.py <mood>          # ambiance: upbeat|chill|epic|corporate|hiphop|tension|happy
  python fetch_music.py <mood> --force  # re-telecharge meme si deja present
  python fetch_music.py --for-tone fun  # choisit l'ambiance selon le ton (fun/pro)
  python fetch_music.py --list
Imprime le chemin relatif du .mp3 (a utiliser comme music.track).
"""
import argparse
import os
import sys
import urllib.request
from common import ROOT, log

MUSIC = os.path.join(ROOT, "remotion", "public", "music")
BASE = "https://assets.mixkit.co/music/{id}/{id}.mp3"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# IDs Mixkit verifies (200 OK). Regroupes par ambiance (best-effort).
MOODS = {
    "upbeat":    [644, 128, 419],
    "chill":     [125, 550, 89],
    "epic":      [765, 616, 203],
    "corporate": [431, 738, 156],
    "hiphop":    [130, 27, 64],
    "tension":   [12, 203, 616],
    "happy":     [644, 419, 128],
}
TONE_MOOD = {"fun": "upbeat", "pro": "corporate"}


def dl(url, dst):
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=60).read()
    if len(data) < 50000:
        raise ValueError(f"trop petit ({len(data)} o)")
    open(dst, "wb").write(data)
    return len(data)


def fetch(mood, force=False):
    if mood not in MOODS:
        log(f"ambiance inconnue '{mood}' -> upbeat")
        mood = "upbeat"
    os.makedirs(MUSIC, exist_ok=True)
    dst = os.path.join(MUSIC, f"{mood}.mp3")
    rel = f"music/{mood}.mp3"
    if os.path.exists(dst) and os.path.getsize(dst) > 50000 and not force:
        log(f"deja present : {rel}")
        return rel
    for i in MOODS[mood]:
        try:
            n = dl(BASE.format(id=i), dst)
            log(f"telecharge {rel} ({n//1024} Ko, id {i})")
            return rel
        except Exception as e:
            log(f"echec id {i}: {str(e)[:80]}")
    log(f"aucune source pour {mood}")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mood", nargs="?")
    ap.add_argument("--for-tone", choices=["fun", "pro"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("Ambiances:", ", ".join(MOODS))
        return
    mood = a.mood or (TONE_MOOD.get(a.for_tone) if a.for_tone else None)
    if not mood:
        ap.print_help()
        sys.exit(1)
    rel = fetch(mood, a.force)
    if rel:
        print(rel)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
