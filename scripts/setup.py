"""Installe tout ce qu'il faut : bruitages (synthese ffmpeg), police, Remotion.

Usage: python setup.py [--skip-npm] [--skip-font]
"""
import argparse
import os
import subprocess
import sys
import urllib.request
from common import FFMPEG, ROOT, run, log

REMOTION = os.path.join(ROOT, "remotion")
PUB = os.path.join(REMOTION, "public")
SFX = os.path.join(PUB, "sfx")
FONTS = os.path.join(PUB, "fonts")

# Bruitages synthetises : coupes net au debut/fin (pas de silence de tete).
SFX_SPECS = {
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.5:c=white:a=0.6",
               "-af", "highpass=f=350,lowpass=f=5500,afade=t=in:st=0:d=0.07,afade=t=out:st=0.28:d=0.22,volume=1.6"],
    "impact": ["-f", "lavfi", "-i", "sine=frequency=72:duration=0.5",
               "-af", "afade=t=in:d=0.004,afade=t=out:st=0.05:d=0.45,volume=2.0"],
    "pop":    ["-f", "lavfi", "-i", "sine=frequency=620:duration=0.12",
               "-af", "afade=t=out:st=0.02:d=0.1,volume=1.2"],
    "click":  ["-f", "lavfi", "-i", "sine=frequency=1500:duration=0.045",
               "-af", "afade=t=out:st=0.005:d=0.04,volume=0.9"],
    "riser":  ["-f", "lavfi", "-i", "aevalsrc=0.32*sin(2*PI*(200+600*t)*t):d=1:s=48000",
               "-af", "afade=t=in:d=0.1,afade=t=out:st=0.85:d=0.15"],
    "ding":   ["-f", "lavfi", "-i", "sine=frequency=1320:duration=0.5",
               "-af", "afade=t=out:st=0.05:d=0.45,volume=0.8"],
    "boom":   ["-f", "lavfi", "-i", "sine=frequency=55:duration=0.7",
               "-af", "afade=t=in:d=0.004,afade=t=out:st=0.1:d=0.6,volume=2.2"],
    "transition": ["-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:a=0.5",
               "-af", "highpass=f=200,lowpass=f=8000,afade=t=in:st=0:d=0.2,afade=t=out:st=0.2:d=0.2,volume=1.4"],
    "notif":  ["-f", "lavfi", "-i", "sine=frequency=880:duration=0.12",
               "-f", "lavfi", "-i", "sine=frequency=1180:duration=0.12",
               "-filter_complex", "[0][1]concat=n=2:v=0:a=1,afade=t=out:st=0.18:d=0.06,volume=0.9"],
    "subscribe": ["-f", "lavfi", "-i", "sine=frequency=660:duration=0.1",
               "-f", "lavfi", "-i", "sine=frequency=990:duration=0.14",
               "-filter_complex", "[0][1]concat=n=2:v=0:a=1,afade=t=out:st=0.2:d=0.04,volume=0.95"],
}

FONT_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-ExtraBold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
]


def synth_sfx():
    """Sons de SECOURS synthetises. La vraie banque vient d'internet via fetch_sfx.py
    (lance ensuite), qui ecrase ces fichiers si le telechargement reussit."""
    os.makedirs(SFX, exist_ok=True)
    for name, args in SFX_SPECS.items():
        out = os.path.join(SFX, f"{name}.wav")
        run([FFMPEG, "-y"] + args + ["-ac", "2", "-ar", "48000", out])
        log(f"sfx (secours): {name}.wav")


def fetch_real_sfx():
    """Telecharge les vrais bruitages (Mixkit) avec auto-trim + filtre qualite."""
    import subprocess
    log("telechargement du soundboard depuis internet (fetch_sfx.py --all)...")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fetch_sfx.py"), "--all"])
    if r.returncode != 0:
        log("soundboard internet partiel/indisponible -> les sons de secours restent en place.")


def get_font(skip):
    if skip:
        return
    os.makedirs(FONTS, exist_ok=True)
    dest = os.path.join(FONTS, "caption.ttf")
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        log("police deja presente.")
        return
    for url in FONT_URLS:
        try:
            log(f"telechargement police: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) > 10000:
                open(dest, "wb").write(data)
                log(f"police OK ({len(data)//1024} Ko).")
                return
        except Exception as e:
            log(f"echec police: {str(e)[:120]}")
    log("police non telechargee -> Remotion utilisera une police systeme (non bloquant).")


def npm_install(skip):
    if skip:
        return
    if os.path.exists(os.path.join(REMOTION, "node_modules")):
        log("node_modules deja present (npm install ignore).")
        return
    npm = "npm.cmd" if os.name == "nt" else "npm"
    log("npm install dans remotion/ (peut prendre 1-3 min)...")
    r = subprocess.run([npm, "install"], cwd=REMOTION)
    if r.returncode != 0:
        log("npm install a echoue. Relance manuellement: cd remotion && npm install")
    else:
        log("Remotion installe.")


def check_whisper():
    try:
        import faster_whisper  # noqa
        log(f"faster-whisper OK ({faster_whisper.__version__}).")
    except Exception as e:
        log(f"faster-whisper indisponible: {str(e)[:120]} (pip install faster-whisper)")


def check_prereqs():
    """Bilan des prerequis du PLAN THEYO : ce qui marche, ce qui manque (optionnel)."""
    import shutil as _sh
    from common import load_dotenv
    load_dotenv()
    log("-- bilan des prerequis du plan --")
    # b-roll YouTube (voie preferee de theyo) : yt-dlp + runtime JS (node)
    try:
        import yt_dlp  # noqa
        ytdlp = getattr(yt_dlp.version, "__version__", "?")
    except Exception:
        ytdlp = None
    node = _sh.which("node")
    if ytdlp and node:
        log(f"b-roll YouTube OK (yt-dlp {ytdlp} + node --js-runtimes).")
    elif ytdlp:
        log("yt-dlp present mais PAS de runtime JS (node/deno) : formats YouTube degrades.")
    else:
        log("yt-dlp absent (pip install yt-dlp) : pas de b-roll YouTube.")
    # les yeux (Gemini)
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        log("Gemini OK (brief avant montage + verdict apres rendu, integres a run.py).")
    else:
        log("GEMINI_API_KEY absent (.env) : les yeux passeront par les frames locales.")
    # transcription Scribe (optionnel, noms propres)
    if os.environ.get("ELEVENLABS_API_KEY"):
        log("ElevenLabs Scribe OK (orthographe des noms propres fusionnee).")
    else:
        log("ELEVENLABS_API_KEY absent (optionnel) : lexicon captions comme fallback.")
    # b-roll stock avec cle
    if os.environ.get("PEXELS_API_KEY"):
        log("Pexels OK (b-roll stock avec cle).")
    else:
        log("PEXELS_API_KEY absent (optionnel) : Openverse sans cle en fallback.")
    # voix en avant (separation Demucs)
    try:
        import torch, demucs  # noqa
        log(f"voice_up OK (demucs + torch, cuda={'oui' if torch.cuda.is_available() else 'non'}).")
    except Exception:
        log("demucs absent : voice_up desactive (pip install torch --index-url "
            "https://download.pytorch.org/whl/cu121 ; pip install demucs).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-npm", action="store_true")
    ap.add_argument("--skip-font", action="store_true")
    a = ap.parse_args()
    log("== SETUP MONTEUR ==")
    synth_sfx()
    fetch_real_sfx()
    get_font(a.skip_font)
    check_whisper()
    npm_install(a.skip_npm)
    check_prereqs()
    log("== SETUP TERMINE ==")


if __name__ == "__main__":
    main()
