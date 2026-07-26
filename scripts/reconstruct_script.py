"""COHERENCE DU RECIT GARDE : reconstruit ce que le SPECTATEUR va reellement entendre
en enchainant uniquement les mots des keep_segments de plan.json, avec chaque coupe
rendue EXPLICITE entre les segments (duree + ce qui a ete retire).

C'est l'etape qui manque quand un montage "n'a aucun sens" alors que chaque coupe prise
individuellement semblait raisonnable : en lisant SEULEMENT le transcript garde, dans
l'ordre, on se met a la place du spectateur qui n'a jamais vu le rush brut. Un pronom
sans antecedent, une reponse sans question, une blague sans mise en place, un "comme
je disais" qui pointe vers du contenu coupe -> invisibles segment par segment, evidents
a la lecture du script reconstruit.

Usage: python reconstruct_script.py work/<nom>
Sortie : le script reconstruit sur stdout, a LIRE EN ENTIER avant d'habiller (etape 5).
Aucune detection automatique de rupture (ca demande de comprendre le sens) : c'est un
outil de LECTURE, le jugement reste a Claude. Prochaine coupe cassee -> corriger
plan.json (etendre le keep, ou ajouter une carte de contexte), relancer, relire.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import log

SENT_END = (".", "!", "?", "...")


def mid_sentence_cut(all_words, t, is_start):
    """Detection OBJECTIVE (pas de jugement de sens necessaire) : une coupe qui tombe
    en PLEIN MILIEU d'une phrase, repere sur le transcript BRUT (pas le garde) — c'est
    la moitie des ruptures qui rendent un montage incomprehensible, et contrairement a
    la coherence semantique (pronoms, callbacks) ca se detecte a coup sur par le code.

    Le signal fiable N'EST PAS la duree du silence (une hesitation de 6s peut couper
    une phrase en deux tout autant qu'un silence de 0.2s — verifie sur un cas reel :
    "Je vais le [pause 6s] mettre ici" est bien UNE phrase malgre la pause) : c'est la
    MAJUSCULE. Le francais (et Whisper) capitalise le premier mot d'une phrase -> un
    mot de reprise en minuscule apres une coupe = presque toujours une coupe en plein
    milieu. Une reprise en Majuscule (ex: "Elle est belle.") est grammaticalement
    complete mais peut quand meme avoir un probleme de SENS (pronom sans antecedent) —
    ca, seule la relecture humaine/Claude peut le voir, pas ce detecteur.
    is_start=True : t est un debut de segment garde -> regarder le mot juste AVANT.
    is_start=False : t est une fin de segment garde -> regarder le mot juste APRES."""
    if is_start:
        after = [w for w in all_words if w["start"] >= t]
        if not after:
            return False
        first = after[0]["w"].strip()
        return bool(first) and first[0].islower()
    else:
        before = [w for w in all_words if w["end"] <= t]
        if not before:
            return False
        last = before[-1]["w"].rstrip()
        after = [w for w in all_words if w["start"] > t]
        if not after:
            return False
        nxt = after[0]["w"].strip()
        return not last.endswith(SENT_END) and bool(nxt) and nxt[0].islower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--out", help="ecrit aussi dans ce fichier (defaut: <work_dir>/script_reconstruit.txt)")
    a = ap.parse_args()
    wd = a.work_dir
    words = json.load(open(os.path.join(wd, "words.json"), encoding="utf-8"))["words"]
    plan = json.load(open(os.path.join(wd, "plan.json"), encoding="utf-8"))
    segs = sorted(plan["keep_segments"], key=lambda s: s["start"])
    if not segs:
        log("plan vide — rien a reconstruire.")
        return

    lines = []
    lines.append("=== SCRIPT RECONSTRUIT (ce que le spectateur entend, dans l'ordre) ===")
    lines.append("Lis ceci comme si tu decouvrais la video pour la premiere fois — tu n'as")
    lines.append("JAMAIS vu ce qui est entre crochets [COUPE ...].\n")

    prev_end = None
    total_kept = 0.0
    total_cut = 0.0
    mid_cuts = []
    for i, s in enumerate(segs):
        t0, t1 = s["start"], s["end"]
        if prev_end is not None and t0 > prev_end + 0.05:
            gap = t0 - prev_end
            total_cut += gap
            # ce qui a ete dit PENDANT le trou (pour que Claude sache ce qu'il a coupe,
            # sans que ca soit confondu avec ce que le spectateur entend)
            cut_words = [w["w"] for w in words if prev_end <= w["start"] < t0]
            apercu = " ".join(cut_words[:25])
            if len(cut_words) > 25:
                apercu += " (...)"
            lines.append(f"\n   [COUPE {gap:.1f}s, {t0-gap:.1f}s->{t0:.1f}s — contenu retire: "
                         f"\"{apercu}\"]" if apercu else f"\n   [COUPE {gap:.1f}s, {t0-gap:.1f}s->{t0:.1f}s]")
            if mid_sentence_cut(words, prev_end, is_start=False):
                mid_cuts.append((prev_end, "fin de segment tombe en pleine phrase"))
            if mid_sentence_cut(words, t0, is_start=True):
                mid_cuts.append((t0, "debut de segment reprend en pleine phrase"))
        seg_words = [w["w"] for w in words if t0 <= w["start"] < t1]
        speed = s.get("speed", 1.0)
        tag = f" (x{speed} timelapse — voix coupee)" if speed >= 3 else ""
        marker = " ⚠ COUPE MI-PHRASE ⚠" if any(abs(tt - t0) < 0.01 for tt, _ in mid_cuts) else ""
        lines.append(f"[{t0:.1f}s]{tag}{marker} " + " ".join(seg_words))
        total_kept += (t1 - t0)
        prev_end = t1

    lines.append(f"\n\n=== BILAN : {total_kept:.0f}s gardees / {total_cut:.0f}s coupees "
                 f"({len(segs)} segments, {len(segs)-1} coupes) ===")
    if mid_cuts:
        lines.append(f"\n⚠ {len(mid_cuts)} COUPE(S) MI-PHRASE DETECTEE(S) AUTOMATIQUEMENT — a corriger")
        lines.append("EN PRIORITE (bug objectif, pas d'ambiguite de sens) : etendre le keep_segment")
        lines.append("jusqu'a la frontiere de phrase la plus proche (silence ou .!?) :")
        for t, why in mid_cuts:
            lines.append(f"  - {t:.1f}s : {why}")
    else:
        lines.append("\n✓ aucune coupe mi-phrase (toutes les frontieres tombent sur un silence "
                     "ou une fin de phrase).")
    lines.append("\nEnsuite, pour CHAQUE [COUPE...] restante, verifier : le segment d'APRES fait-il")
    lines.append("reference a un truc dit dans le [COUPE...] (pronom 'il/ça', 'comme je disais',")
    lines.append("reponse a une question posee avant la coupe, blague sans sa mise en place) ? Si")
    lines.append("oui -> etendre le keep_segment pour englober le contexte manquant, ou ajouter un")
    lines.append("`card`/`callout` bref qui donne l'info manquante a l'ecran. Relancer ce script,")
    lines.append("relire, jusqu'a ce que le recit garde se tienne SEUL, sans le rush brut en tete.")

    out = "\n".join(lines)
    print(out)
    dest = a.out or os.path.join(wd, "script_reconstruit.txt")
    open(dest, "w", encoding="utf-8").write(out)
    log(f"\n(ecrit aussi dans {dest})")
    if mid_cuts:
        log(f"⚠ {len(mid_cuts)} coupe(s) mi-phrase — corriger plan.json avant de continuer.")


if __name__ == "__main__":
    main()
