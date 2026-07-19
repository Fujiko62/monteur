"""Post-traite plan.json : absorbe les micro-coupes (anti-clignotement),
retire des plages ennuyeuses (chargements, temps morts) et PROTEGE des silences
voulus (pause dramatique, suspense) donnes en JSON.

Usage:
  python scripts/rework_plan.py <work_dir> --absorb-gaps 2.5 [--remove boring.json]
                                [--protect protect.json]

boring.json / protect.json: [{"start": s, "end": e}, ...] en secondes (time_base original).
--protect annule toute coupe qui chevauche une plage : le blanc RESTE dans le montage
(les "silences a garder" du plan theyo).
"""
import argparse, json, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir")
    ap.add_argument("--absorb-gaps", type=float, default=2.5,
                    help="les coupes plus courtes que ca sont annulees (le blanc est garde)")
    ap.add_argument("--remove", default=None, help="JSON de plages a retirer de force")
    ap.add_argument("--protect", default=None,
                    help="JSON de plages de silence a GARDER (annule les coupes dessus)")
    args = ap.parse_args()

    wd = Path(args.work_dir)
    plan_path = wd / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    segs = [[s["start"], s["end"]] for s in plan["keep_segments"]]

    # 1) anti-clignotement : fusionner les segments separes par une petite coupe.
    # gap NEGATIF = liste non chronologique (ex: cold-open en tete) -> ne JAMAIS fusionner
    # (sinon le teaser avale tout ce qui suit).
    merged = [segs[0]]
    absorbed = 0
    for s, e in segs[1:]:
        gap = s - merged[-1][1]
        if 0 <= gap < args.absorb_gaps:
            merged[-1][1] = max(merged[-1][1], e)
            absorbed += 1
        else:
            merged.append([s, e])

    # 2) retirer les plages ennuyeuses (chargements, temps morts)
    removed_s = 0.0
    if args.remove:
        boring = json.loads(Path(args.remove).read_text(encoding="utf-8"))
        for br in boring:
            a, b = float(br["start"]), float(br["end"])
            out = []
            for s, e in merged:
                if e <= a or s >= b:          # pas de chevauchement
                    out.append([s, e])
                else:
                    if s < a: out.append([s, a])
                    if e > b: out.append([b, e])
                    removed_s += min(e, b) - max(s, a)
            merged = out
        merged = [[s, e] for s, e in merged if e - s > 0.4]

    # 3) proteger des silences voulus : annuler toute coupe qui les chevauche
    protected_n = 0
    if args.protect:
        keep_ranges = json.loads(Path(args.protect).read_text(encoding="utf-8"))
        out = [merged[0]]
        for s, e in merged[1:]:
            gap_a, gap_b = out[-1][1], s
            if any(max(gap_a, float(p["start"])) < min(gap_b, float(p["end"]))
                   for p in keep_ranges):
                out[-1][1] = max(out[-1][1], e)   # la coupe saute, le blanc reste
                protected_n += 1
            else:
                out.append([s, e])
        merged = out

    plan["keep_segments"] = [{"start": round(s, 3), "end": round(e, 3)} for s, e in merged]
    dur = sum(e - s for s, e in merged)
    plan.setdefault("stats", {})["cut_duration"] = round(dur, 2)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[rework] {absorbed} micro-coupes absorbees, {removed_s:.1f}s ennuyeuses retirees, "
          f"{protected_n} silences proteges, {len(merged)} segments, duree gardee {dur:.1f}s")

if __name__ == "__main__":
    main()
