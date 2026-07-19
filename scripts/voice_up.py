"""VOIX EN AVANT : separe la voix du reste (jeu/musique source) par IA locale (Demucs,
GPU) et remixe avec la voix boostee + le fond baisse. C'est LA reponse au defaut n1
des enregistrements gameplay : la voix du createur mixee trop bas contre le jeu,
irrattrapable par un simple EQ puisque tout est sur la meme piste.

Usage:
  python voice_up.py <video> [--out <video_out>] [--voice-gain 5] [--bed-gain -6]
                     [--model htdemucs] [--no-speechnorm]
La video n'est PAS re-rendue : seul l'audio est traite puis re-muxe (rapide).
Requiert: pip install demucs (torch CUDA conseille). Fallback sans demucs: erreur claire.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from common import FFMPEG, run, log, die, ffprobe_info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--voice-gain", type=float, default=5.0, help="boost voix (dB)")
    ap.add_argument("--bed-gain", type=float, default=-6.0, help="gain du fond (dB)")
    ap.add_argument("--model", default="htdemucs")
    ap.add_argument("--no-speechnorm", action="store_true",
                    help="ne pas lisser le niveau de la voix (speechnorm)")
    a = ap.parse_args()
    if not os.path.exists(a.video):
        die(f"video introuvable: {a.video}")
    out = a.out or (os.path.splitext(a.video)[0] + "_voiceup.mp4")

    try:
        import demucs  # noqa
    except ImportError:
        die("demucs absent. Installe: pip install demucs (torch CUDA conseille).")

    with tempfile.TemporaryDirectory(prefix="voiceup_") as td:
        src = os.path.join(td, "audio.wav")
        log("extraction audio...")
        run([FFMPEG, "-y", "-i", a.video, "-vn", "-ac", "2", "-ar", "44100",
             "-c:a", "pcm_s16le", src])

        log(f"separation voix/fond (demucs {a.model}, GPU si dispo — ~1-2 min / 10 min)...")
        r = subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals",
                            "-n", a.model, "-o", td, src])
        if r.returncode != 0:
            die("demucs a echoue.")
        stems = glob.glob(os.path.join(td, a.model, "*", "vocals.wav"))
        beds = glob.glob(os.path.join(td, a.model, "*", "no_vocals.wav"))
        if not stems or not beds:
            die("stems demucs introuvables.")
        vocals, bed = stems[0], beds[0]

        # remix : voix lissee (speechnorm doux) + boostee, fond baisse, limiteur final
        vchain = f"volume={a.voice_gain}dB"
        if not a.no_speechnorm:
            vchain = f"speechnorm=e=3:r=0.0002:l=1,{vchain}"
        fc = (f"[0:a]{vchain}[v];"
              f"[1:a]volume={a.bed_gain}dB[b];"
              f"[v][b]amix=inputs=2:duration=longest:normalize=0,"
              f"alimiter=limit=0.97:level=false[a]")
        mixed = os.path.join(td, "mix.wav")
        log(f"remix voix {a.voice_gain:+.0f}dB / fond {a.bed_gain:+.0f}dB...")
        run([FFMPEG, "-y", "-i", vocals, "-i", bed, "-filter_complex", fc,
             "-map", "[a]", "-ar", "48000", "-ac", "2", mixed])

        log("re-mux (video intacte, pas de re-rendu)...")
        run([FFMPEG, "-y", "-i", a.video, "-i", mixed, "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", out])
    log(f"OK: {out}")
    print(out)


if __name__ == "__main__":
    main()
