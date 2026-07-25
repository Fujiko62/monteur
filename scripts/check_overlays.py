"""Verifie overlays.json AVANT le build : ce qui se voit mal a la lecture d'un JSON mais
saute aux yeux dans la video (deux sprites en meme temps, sprite inexistant, elements
empiles au meme endroit, effet plus long que la scene...).

Usage: python check_overlays.py work/<nom>
Sortie : PASS/FAIL par regle, code retour 1 si un FAIL (a corriger avant build_cut).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, log

FAILS, WARNS = [], []


def check(ok, label, warn=False):
    print(f"  [{'PASS' if ok else ('WARN' if warn else 'FAIL')}] {label}")
    if not ok:
        (WARNS if warn else FAILS).append(label)


def span(o):
    s = float(o.get("start", 0))
    return s, s + float(o.get("dur", 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    a = ap.parse_args()
    path = os.path.join(a.work_dir, "overlays.json")
    if not os.path.exists(path):
        log("pas d'overlays.json — rien a verifier.")
        return
    data = json.load(open(path, encoding="utf-8"))
    ov = data.get("overlays", data) if isinstance(data, dict) else data
    print(f"=== CONTROLE OVERLAYS : {len(ov)} elements ===")

    # --- SPRITES : un seul a l'ecran, et il doit exister ---
    sprites = sorted([o for o in ov if o.get("type") == "sprite"], key=lambda o: o.get("start", 0))
    print(f"- Sprites ({len(sprites)})")
    if sprites:
        idx_path = os.path.join(ROOT, "remotion", "public", "sprite", "index.json")
        known = set(json.load(open(idx_path, encoding="utf-8"))) if os.path.exists(idx_path) else set()
        for o in sprites:
            n = (o.get("params") or {}).get("name")
            check(n in known, f"sprite '{n}' existe dans sprite/index.json")

        # REGLE ABSOLUE (exigence utilisateur) : JAMAIS deux sprites simultanes.
        overlaps = []
        for i in range(len(sprites) - 1):
            s1, e1 = span(sprites[i])
            s2, _ = span(sprites[i + 1])
            if s2 < e1:
                n1 = (sprites[i].get("params") or {}).get("name")
                n2 = (sprites[i + 1].get("params") or {}).get("name")
                overlaps.append(f"{n1}@{s1:.1f}-{e1:.1f} recouvre {n2}@{s2:.1f}")
        check(not overlaps, f"jamais deux sprites en meme temps ({overlaps or 'aucun chevauchement'})")

        # respiration : deux sprites colles bout a bout donnent un defile de mascottes
        tights = [f"{s2:.1f}" for i in range(len(sprites) - 1)
                  for s2 in [span(sprites[i + 1])[0]] if 0 <= s2 - span(sprites[i])[1] < 4]
        check(not tights, f"au moins 4 s entre deux sprites ({tights or 'ok'})", warn=True)

        durs = [round(e - s, 1) for s, e in map(span, sprites)]
        check(all(1.0 <= d <= 5.0 for d in durs), f"durees entre 1 et 5 s ({durs})", warn=True)
        check(all((o.get("params") or {}).get("idle", "bob") != "none" for o in sprites),
              "aucun sprite statique (idle actif) — une image posee est morte a l'ecran")

    # --- COLLISIONS generales : deux elements TEXTE au meme endroit au meme moment ---
    print("- Collisions")
    textish = [o for o in ov if o.get("type") in ("callout", "card", "stat", "big_stat")
               or (o.get("type") == "fx" and o.get("name") in ("callout", "big_stat", "stat_panel", "title_card"))]
    coll = []
    for i in range(len(textish)):
        for j in range(i + 1, len(textish)):
            s1, e1 = span(textish[i])
            s2, e2 = span(textish[j])
            if s1 < e2 and s2 < e1:
                coll.append(f"{textish[i].get('type')}@{s1:.1f} + {textish[j].get('type')}@{s2:.1f}")
    check(not coll, f"pas deux textes simultanes ({coll or 'aucun'})", warn=True)

    print()
    if FAILS:
        log(f"ECHEC : {len(FAILS)} probleme(s). Corriger overlays.json AVANT build_cut.")
        sys.exit(1)
    log(f"OVERLAYS OK ({len(WARNS)} avertissement(s)).")


if __name__ == "__main__":
    main()
