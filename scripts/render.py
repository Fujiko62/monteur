"""Rendu final via Remotion : copie les assets et lance le render.

Usage: python render.py <work_dir> <output.mp4>
"""
import argparse
import os
import shutil
import subprocess
import sys
from common import ROOT, log, die, load_json

REMOTION = os.path.join(ROOT, "remotion")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("output")
    ap.add_argument("--concurrency", default=None)
    a = ap.parse_args()

    cut = os.path.join(a.work_dir, "cut.mp4")
    props = os.path.join(a.work_dir, "props.json")
    for f in (cut, props):
        if not os.path.exists(f):
            die(f"manquant: {f} (lance d'abord build_cut.py)")

    pub = os.path.join(REMOTION, "public")
    os.makedirs(pub, exist_ok=True)
    shutil.copy(cut, os.path.join(pub, "cut.mp4"))

    if not os.path.exists(os.path.join(REMOTION, "node_modules")):
        die("dependances Remotion absentes. Lance: python scripts/setup.py")
    if not os.path.exists(os.path.join(pub, "fonts", "caption.ttf")):
        log("ATTENTION: police caption.ttf absente (setup.py). Rendu avec police systeme.")

    out = os.path.abspath(a.output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    npx = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [npx, "remotion", "render", "src/index.ts", "Reel", out,
           f"--props={os.path.abspath(props)}",
           f"--crf={os.environ.get('MONTEUR_CRF', '21')}",
           # extraction OffthreadVideo d'une longue video : le timeout par defaut (28s)
           # saute au demarrage sous forte concurrence -> 120s.
           f"--timeout={os.environ.get('MONTEUR_TIMEOUT_MS', '120000')}"]
    if a.concurrency:
        cmd.append(f"--concurrency={a.concurrency}")
    log("rendu Remotion en cours (premier rendu = telechargement du navigateur headless)...")
    # bundles temporaires Remotion sur le disque DATA (D: KingSpec) : ils pesent des Go
    # et ont deja rempli C: (lecon #22). MONTEUR_TMP pour changer.
    env = dict(os.environ)
    tmp = os.environ.get("MONTEUR_TMP", r"D:\montage claude\tmp")
    try:
        os.makedirs(tmp, exist_ok=True)
        env["TEMP"] = env["TMP"] = tmp
    except OSError:
        pass  # disque absent -> temp par defaut
    r = subprocess.run(cmd, cwd=REMOTION, env=env)
    if r.returncode != 0:
        die("le rendu Remotion a echoue (voir sortie ci-dessus).")
    log(f"OK: {out}")


if __name__ == "__main__":
    main()
