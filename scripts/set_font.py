"""Change LA police du montage (etape "LA PATTE" du plan theyo : "les polices c'est
extremement important, encore plus en video verticale").

Regenere remotion/src/fontData.ts (data-URI base64, technique validee : PAS de
delayRender, pas de reseau au rendu — voir erreur connue #1 du SKILL).

Usage:
  python scripts/set_font.py "Bebas Neue"            # nom Google Fonts (poids 800 si dispo)
  python scripts/set_font.py "Inter" --weight 900
  python scripts/set_font.py --file "C:/chemin/MaPolice.ttf"
  python scripts/set_font.py --list                  # suggestions de polices qui marchent

Apres changement : le prochain rendu utilise la nouvelle police partout (sous-titres,
callouts, schemas, title_card, miniature). Mets aussi captions.font_family a jour dans
config.json (purement informatif).
"""
import argparse
import base64
import os
import re
import sys
import urllib.request
from common import ROOT, log, die

FONTDATA = os.path.join(ROOT, "remotion", "src", "fontData.ts")

SUGGESTIONS = [
    ("Montserrat", "geometrique, moderne (defaut du monteur)"),
    ("Bebas Neue", "condensee, GROS titres viraux"),
    ("Anton", "ultra-bold, impact maximal"),
    ("Poppins", "ronde, sympathique"),
    ("Inter", "neutre, tres lisible, tech"),
    ("Archivo Black", "carree, punchy"),
    ("Oswald", "condensee, editoriale"),
]


def google_font_ttf(name, weight):
    """Recupere l'URL du TTF via l'API CSS de Google Fonts (sans cle)."""
    fam = name.strip().replace(" ", "+")
    css_url = f"https://fonts.googleapis.com/css2?family={fam}:wght@{weight}"
    req = urllib.request.Request(css_url, headers={"User-Agent": "curl/8"})  # UA simple => TTF
    css = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    m = re.search(r"url\((https://[^)]+\.ttf)\)", css)
    if not m:
        die(f"pas de TTF trouve pour '{name}' (poids {weight}). Essaie un autre poids "
            f"ou --file avec un .ttf local.")
    return urllib.request.urlopen(
        urllib.request.Request(m.group(1), headers={"User-Agent": "curl/8"}), timeout=60).read()


def write_fontdata(data, label):
    b64 = base64.b64encode(data).decode("ascii")
    with open(FONTDATA, "w", encoding="utf-8") as f:
        f.write("// Police embarquee en data-URI (pas de fetch reseau -> chargement fiable au rendu).\n")
        f.write(f"// Generee par scripts/set_font.py — {label}\n")
        f.write(f'export const FONT_DATA = "data:font/ttf;base64,{b64}";\n')
    log(f"fontData.ts regenere ({len(data)//1024} Ko) — police active au prochain rendu: {label}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="nom Google Fonts (ex: 'Bebas Neue')")
    ap.add_argument("--weight", type=int, default=800)
    ap.add_argument("--file", help="chemin d'un .ttf/.otf local")
    ap.add_argument("--list", action="store_true", help="suggestions de polices")
    a = ap.parse_args()
    if a.list:
        for n, d in SUGGESTIONS:
            print(f"  {n:<16} {d}")
        return
    if a.file:
        if not os.path.exists(a.file):
            die(f"fichier introuvable: {a.file}")
        data = open(a.file, "rb").read()
        if len(data) < 10000:
            die("fichier trop petit pour etre une police valide.")
        write_fontdata(data, os.path.basename(a.file))
        return
    if not a.name:
        die("donne un nom Google Fonts, --file <ttf>, ou --list.")
    for w in (a.weight, 800, 700, 400):
        try:
            data = google_font_ttf(a.name, w)
            write_fontdata(data, f"{a.name} {w} (Google Fonts)")
            return
        except SystemExit:
            raise
        except Exception as e:
            log(f"poids {w} indisponible: {str(e)[:100]}")
    die(f"impossible de recuperer '{a.name}' sur Google Fonts.")


if __name__ == "__main__":
    main()
