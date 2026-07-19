"""B-roll : extrait VIDEO YouTube (l'arme secrete de theyo). Telecharge UNIQUEMENT le
segment voulu via yt-dlp, dans remotion/public/media/, pret pour un overlay image (mp4).

Le plan theyo : "un MCP YouTube peut [...] recuperer le transcript time code et donc faire
les bonnes coupes au bon moment". Ici : --find "une phrase" telecharge les sous-titres
de la video, localise la phrase et cale --start automatiquement.

ATTENTION DROITS : n'utiliser que des extraits courts a titre d'illustration, sources libres
ou dont tu as le droit. Toujours verifier avant publication.

Usage:
  python fetch_youtube_clip.py "requete ou URL" --name clipA --start 62 --dur 6
  python fetch_youtube_clip.py "URL" --name clipB --find "le moment ou il dit ca" --dur 6
Imprime le nom de fichier (a utiliser comme "src" d'un overlay image, mode fullscreen).
"""
import argparse
import glob
import os
import re
import sys
import subprocess
import tempfile
import unicodedata
from common import FFMPEG, ROOT, log, die

MEDIA = os.path.join(ROOT, "remotion", "public", "media")

# yt-dlp exige un runtime JS pour les formats YouTube recents. deno est son defaut,
# mais Node (deja requis par Remotion) marche aussi : on l'active explicitement.
JS_RUNTIME_ARGS = ["--js-runtimes", "node"]


def hhmmss(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", t.lower())


def find_in_transcript(target, phrase, lang="fr"):
    """Telecharge les sous-titres (auto) de la video et retourne le timestamp (s) du
    passage qui matche le mieux la phrase — le 'transcript time code' du plan theyo."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "subs")
        r = subprocess.run([sys.executable, "-m", "yt_dlp", target, *JS_RUNTIME_ARGS,
                            "--skip-download", "--write-auto-subs", "--write-subs",
                            "--sub-langs", f"{lang}.*,{lang}", "--sub-format", "vtt",
                            "-o", out, "--no-playlist", "--quiet", "--no-warnings"],
                           capture_output=True, text=True)
        vtts = glob.glob(os.path.join(td, "subs*.vtt"))
        if not vtts:
            die(f"pas de sous-titres trouves pour cette video (--find impossible)."
                f"\n{(r.stderr or '')[:200]}")
        # parse VTT : blocs "hh:mm:ss.mmm --> ..." + texte
        cues = []
        cur_t = None
        for line in open(vtts[0], encoding="utf-8"):
            m = re.match(r"(\d+):(\d+):([\d.]+)\s*-->", line)
            if m:
                cur_t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                continue
            txt = re.sub(r"<[^>]+>", "", line).strip()
            if cur_t is not None and txt:
                cues.append((cur_t, _norm(txt)))
        want = _norm(phrase).split()
        if not want or not cues:
            die("--find : phrase ou sous-titres vides.")
        best_t, best_score = None, 0
        for i in range(len(cues)):
            window = " ".join(txt for _, txt in cues[i:i + 4])
            score = sum(1 for w in want if w in window)
            if score > best_score:
                best_t, best_score = cues[i][0], score
        if best_t is None or best_score < max(1, len(want) // 2):
            die(f"--find : passage introuvable dans le transcript (meilleur score "
                f"{best_score}/{len(want)}).")
        log(f"--find : passage trouve a {best_t:.0f}s (score {best_score}/{len(want)}).")
        return best_t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--name", required=True)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--find", default=None,
                    help="phrase a localiser dans le transcript de la video -> cale --start")
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--dur", type=float, default=6)
    ap.add_argument("--height", type=int, default=1080)
    a = ap.parse_args()
    os.makedirs(MEDIA, exist_ok=True)

    target = a.query if a.query.startswith("http") else f"ytsearch1:{a.query}"
    if a.find:
        a.start = max(0.0, find_in_transcript(target, a.find, a.lang) - 0.5)
    section = f"*{hhmmss(a.start)}-{hhmmss(a.start + a.dur)}"
    raw = os.path.join(MEDIA, f"_{a.name}_raw.%(ext)s")
    out = os.path.join(MEDIA, f"{a.name}.mp4")

    cmd = [sys.executable, "-m", "yt_dlp", target, *JS_RUNTIME_ARGS,
           "--download-sections", section, "--force-keyframes-at-cuts",
           "-f", f"bv*[height<={a.height}]+ba/b[height<={a.height}]",
           "--recode-video", "mp4",
           "-o", raw, "--no-playlist", "--quiet", "--no-warnings"]
    log(f"telechargement extrait ({section}) de {target[:60]}...")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die("yt-dlp a echoue (droits, format, ou reseau).")

    # retrouve le fichier telecharge et normalise
    hits = glob.glob(os.path.join(MEDIA, f"_{a.name}_raw.*"))
    if not hits:
        die("aucun fichier telecharge.")
    from common import run
    run([FFMPEG, "-y", "-i", hits[0], "-t", f"{a.dur:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an",
         "-pix_fmt", "yuv420p", out])
    for h in hits:
        os.remove(h)
    log(f"extrait YouTube: {a.name}.mp4")
    print(f"{a.name}.mp4")


if __name__ == "__main__":
    main()
