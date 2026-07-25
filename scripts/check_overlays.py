"""Verifie overlays.json AVANT le build : ce qui se voit mal a la lecture d'un JSON mais
saute aux yeux dans la video (elements empiles au meme endroit, effet plus long
que la scene...).

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
