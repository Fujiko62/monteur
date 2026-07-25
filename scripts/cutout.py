"""DETOURAGE : decoupe UN visuel (ou une case d'une planche/capture) et le sort en PNG
transparent haute qualite, pret a illustrer dans les videos.

A utiliser des qu'il faut ILLUSTRER un objet/sujet : mieux vaut une vraie image
decoupee qu'un pictogramme dessine a la main en code.

Concu pour les captures/photos d'ecran (moire, halo, fond degrade). Le traitement :
  1. cadre la cellule (grille 4x3 ou 3x3) et isole le sprite
  2. anti-moire : median + bilateral leger (l'illustration en aplats se nettoie sans flouter)
  3. detourage EXACT : le fond clair/desature connecte au bord devient transparent
     (les dents et le blanc des yeux, eux, sont a l'interieur -> conserves)
  4. upscale x4 Lanczos + rehaussement de contours (aplats -> bords nets)

Usage:
  python cutout.py <planche.jpg> --grid 4x3 --cell 2,3 --name colere-poing-leve
  python cutout.py <planche.jpg> --grid 3x3 --preview        # planche annotee
Sortie : remotion/public/media/<name>.png (+ entree dans media/index.json)
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, log, die

OUT_DIR = os.path.join(ROOT, "remotion", "public", "media")


def cell_box(w, h, grid, row, col, pad=0.02):
    """Boite d'une cellule de la grille, avec une marge pour absorber la perspective.
    Marge HAUTE nulle (voire negative) : les poses de la rangee du dessus descendent
    leur buste dans la case suivante et polluent le detourage (vecu)."""
    cols, rows = grid
    cw, ch = w / cols, h / rows
    x0 = max(0, int((col - 1) * cw - cw * pad))
    y0 = max(0, int((row - 1) * ch + ch * 0.015))
    x1 = min(w, int(col * cw + cw * pad))
    y1 = min(h, int(row * ch + ch * pad))
    return x0, y0, x1, y1


def background_mask(rgb):
    """True = fond. Fond de la photo : clair ET peu sature. La peau (peche) est plus
    saturee, les cheveux/vetements sont sombres -> seuls le fond et les blancs purs
    passent ; les blancs internes (dents, yeux) sont recuperes ensuite par la
    connexite au bord."""
    a = rgb.astype(np.float32) / 255.0
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return (mx > 0.52) & (sat < 0.22)


def flood_from_border(mask):
    """Garde uniquement la partie du masque CONNECTEE au bord de l'image (le vrai fond).
    BFS iterative en numpy (pas de scipy) : dilatation contrainte jusqu'a stabilite."""
    h, w = mask.shape
    reach = np.zeros_like(mask)
    reach[0, :] |= mask[0, :]
    reach[-1, :] |= mask[-1, :]
    reach[:, 0] |= mask[:, 0]
    reach[:, -1] |= mask[:, -1]
    while True:
        grown = reach.copy()
        grown[1:, :] |= reach[:-1, :]
        grown[:-1, :] |= reach[1:, :]
        grown[:, 1:] |= reach[:, :-1]
        grown[:, :-1] |= reach[:, 1:]
        grown &= mask
        if grown.sum() == reach.sum():
            return grown
        reach = grown


def label_components(fg):
    """Etiquetage des composantes connexes (4-voisins) par propagation numpy — evite
    scipy. Retourne un tableau d'entiers (0 = fond)."""
    h, w = fg.shape
    lab = np.where(fg, np.arange(1, h * w + 1).reshape(h, w), 0)
    while True:
        prev = lab
        m = lab.copy()
        m[1:, :] = np.maximum(m[1:, :], lab[:-1, :])
        m[:-1, :] = np.maximum(m[:-1, :], lab[1:, :])
        m[:, 1:] = np.maximum(m[:, 1:], lab[:, :-1])
        m[:, :-1] = np.maximum(m[:, :-1], lab[:, 1:])
        lab = np.where(fg, m, 0)
        if np.array_equal(lab, prev):
            return lab


def keep_sprite_only(fg, near_px=28, min_ratio=0.03):
    """Ne garde que le SUJET : la plus grosse composante + ses satellites proches
    (micro tenu a bout de bras, batte...). Jette le texte de l'interface du jeu et les
    poussieres/reflets de la photo — sinon ils partent dans le PNG (vecu)."""
    lab = label_components(fg)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    if len(ids) == 0:
        return fg
    main = ids[counts.argmax()]
    main_area = counts.max()

    def bbox(mask):
        ys, xs = np.where(mask)
        return ys.min(), ys.max(), xs.min(), xs.max()

    my0, my1, mx0, mx1 = bbox(lab == main)
    keep = (lab == main)
    for i, area in zip(ids, counts):
        if i == main or area < main_area * min_ratio:
            continue
        y0, y1, x0, x1 = bbox(lab == i)
        # distance entre les deux boites (0 si elles se chevauchent)
        dy = max(0, max(my0 - y1, y0 - my1))
        dx = max(0, max(mx0 - x1, x0 - mx1))
        if (dy * dy + dx * dx) ** 0.5 <= near_px:
            keep |= (lab == i)
    return keep


def clean_sprite(im, scale=4):
    """Photo d'ecran -> sprite PNG transparent net."""
    # 1. anti-moire AVANT tout : la moire est un bruit haute frequence regulier,
    #    un median la supprime sans manger les aplats.
    im = im.filter(ImageFilter.MedianFilter(size=3))
    im = im.filter(ImageFilter.SMOOTH)

    rgb = np.array(im.convert("RGB"))
    bg = flood_from_border(background_mask(rgb))
    fg = keep_sprite_only(~bg)
    alpha = np.where(fg, 255, 0).astype(np.uint8)

    ys, xs = np.where(alpha > 0)
    if len(ys) == 0:
        return None
    # marge de 2 px puis recadrage serre sur le sprite
    y0, y1 = max(0, ys.min() - 2), min(alpha.shape[0], ys.max() + 3)
    x0, x1 = max(0, xs.min() - 2), min(alpha.shape[1], xs.max() + 3)

    out = Image.fromarray(np.dstack([rgb, alpha]), "RGBA").crop((x0, y0, x1, y1))
    r, g, b, a = out.split()
    flat = Image.merge("RGB", (r, g, b))
    # 2. ANTI-MOIRE ADAPTATIF : le moire est un motif periodique ; un median assez large
    #    pour couvrir sa periode l'efface, tout en preservant les contours (contrairement
    #    a un flou). Rayon proportionnel a la taille du sprite : un gros plan a un moire
    #    plus large qu'une vignette. NE PAS quantifier ici : sur du moire, la
    #    quantification cree des taches de couleur (essaye, c'est pire).
    #    Cale par comparaison visuelle (5/9/13) : 9 tue le moire d'un gros plan ~300 px
    #    sans arrondir les angles ; 13 commence a manger la bouche et les meches.
    k = 3 if max(flat.size) < 200 else (5 if max(flat.size) < 265 else 9)
    flat = flat.filter(ImageFilter.MedianFilter(size=k))
    out = Image.merge("RGBA", (*flat.split(), a))
    # 3. upscale : Lanczos sur des aplats = bords propres, puis on redurcit
    out = out.resize((out.width * scale, out.height * scale), Image.LANCZOS)
    r, g, b, a = out.split()
    rgb_i = Image.merge("RGB", (r, g, b)).filter(
        ImageFilter.UnsharpMask(radius=3, percent=110, threshold=2))
    # alpha durci : pas de halo semi-transparent autour du sprite
    a = a.point(lambda v: 0 if v < 110 else 255).filter(ImageFilter.SMOOTH)
    out = Image.merge("RGBA", (*rgb_i.split(), a))
    return out


def preview(path, grid):
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    cols, rows = grid
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            x0, y0, x1, y1 = cell_box(im.width, im.height, grid, r, c, pad=0)
            d.rectangle([x0, y0, x1, y1], outline=(255, 0, 255), width=4)
            d.text((x0 + 10, y0 + 10), f"{r},{c}", fill=(255, 255, 0))
    out = os.path.splitext(path)[0] + "_grille.jpg"
    im.save(out, quality=88)
    log(f"grille: {out}")
    print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planche")
    ap.add_argument("--grid", default="4x3", help="colonnesXlignes, ex 4x3 ou 3x3")
    ap.add_argument("--cell", help="ligne,colonne (1-indexe)")
    ap.add_argument("--name", help="nom parlant : <emotion>-<pose>, ex colere-poing-leve")
    ap.add_argument("--emotion", help="pour l'index (defaut: 1re partie du nom)")
    ap.add_argument("--pose", help="pour l'index (defaut: reste du nom)")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()

    cols, rows = (int(v) for v in a.grid.lower().split("x"))
    if a.preview:
        return preview(a.planche, (cols, rows))
    if not a.cell or not a.name:
        die("donne --cell ligne,colonne et --name <emotion>-<pose> (ou --preview).")

    row, col = (int(v) for v in a.cell.split(","))
    im = Image.open(a.planche).convert("RGB")
    box = cell_box(im.width, im.height, (cols, rows), row, col)
    sprite = clean_sprite(im.crop(box), a.scale)
    if sprite is None:
        die(f"cellule {a.cell} vide (aucun sprite detecte).")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{a.name}.png")
    sprite.save(out)

    # index : permet de retrouver un visuel PAR SON SENS, pas par son nom de fichier
    idx_path = os.path.join(OUT_DIR, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    parts = a.name.split("-")
    idx[a.name] = {
        "file": f"{a.name}.png",
        "emotion": a.emotion or parts[0],
        "pose": a.pose or "-".join(parts[1:]),
        "w": sprite.width, "h": sprite.height,
        "source": f"{os.path.basename(a.planche)} {a.grid} cell {a.cell}",
    }
    json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"DECOUPE: {out} ({sprite.width}x{sprite.height}) [{idx[a.name]['emotion']} / {idx[a.name]['pose']}]")
    print(out)


if __name__ == "__main__":
    main()
