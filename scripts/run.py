"""Pipeline AUTONOME complet : tu envoies une video, il sort le montage pret a poster.

C'est LE PLAN THEYO integre en une commande, dans l'ordre :
  transcribe -> brief (les yeux AVANT : Gemini analyse la video brute) -> plan (coupe)
  -> auto (ton + animations proposees) -> cut -> render -> music -> review (les yeux
  APRES : frames ciblees + verdict Gemini PREPONDERANT sur le fichier LIVRE).

Par defaut il fait TOUT tout seul. Sans GEMINI_API_KEY : brief et review Gemini sont
sautes proprement (fallback frames locales), le reste tourne pareil.

Usage:
  python run.py <video>                  # 100% auto
  python run.py <video> --tone pro       # force le ton (fun/pro/auto)
  python run.py <video> --no-overlays    # pas d'animations auto
  python run.py <video> --no-music       # pas de musique
  python run.py <video> --no-review      # pas de boucle des yeux (deconseille)
  python run.py <video> --from cut       # reprendre a une etape
Etapes: transcribe -> brief -> plan -> auto -> cut -> render -> music -> review
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from common import ROOT, log, die, load_json, save_json, load_config, project_dir, safe_name

STAGES = ["transcribe", "brief", "plan", "auto", "cut", "render", "music", "review"]
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def sh(mod, *args, capture=False, tolerate=()):
    """Lance un script du pipeline. tolerate = codes de sortie non-fatals (ex: brief
    sans cle Gemini) : on log et on continue."""
    cmd = [sys.executable, os.path.join(SCRIPTS, mod)] + [str(x) for x in args]
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and r.returncode not in tolerate:
            die(f"etape {mod} echouee.\n{r.stderr}")
        return r.returncode, r.stdout.strip()
    r = subprocess.run(cmd)
    if r.returncode != 0 and r.returncode not in tolerate:
        die(f"etape {mod} echouee.")
    return r.returncode, ""


def promote_overlays(work, force):
    """Branche overlays.suggested.json -> overlays.json SANS ecraser un montage authored
    (erreur connue #19). Un overlays.json ecrit par cette etape porte _generated_by=auto ;
    tout autre overlays.json est considere fait main et donc conserve."""
    sug = os.path.join(work, "overlays.suggested.json")
    dst = os.path.join(work, "overlays.json")
    if not os.path.exists(sug):
        return None
    if os.path.exists(dst) and not force:
        cur = load_json(dst)
        if not (isinstance(cur, dict) and cur.get("_generated_by") == "auto"):
            log("overlays.json AUTHORED detecte -> conserve tel quel (lecon #19). "
                "--force-overlays pour repartir de la suggestion.")
            return load_json(sug).get("_tone")
    data = load_json(sug)
    data["_generated_by"] = "auto"
    save_json(dst, data)
    log(f"animations auto appliquees (ton={data.get('_tone')}).")
    return data.get("_tone")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--work", default=None)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--tone", default="auto", choices=["auto", "fun", "pro"])
    ap.add_argument("--no-overlays", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--force-overlays", action="store_true",
                    help="ecrase un overlays.json meme authored par la suggestion auto")
    ap.add_argument("--from", dest="start", default="transcribe", choices=STAGES)
    ap.add_argument("--only", default=None, choices=STAGES)
    a = ap.parse_args()

    if not os.path.exists(a.video):
        die(f"video introuvable: {a.video}")
    base = os.path.splitext(os.path.basename(a.video))[0]
    safe = safe_name(a.video)
    work = a.work or os.path.join(ROOT, "work", safe)
    os.makedirs(work, exist_ok=True)
    proj = project_dir(a.video)  # livraisons/<nom>/ : une video = un dossier range
    render_out = os.path.join(work, f"{safe}_render.mp4")
    final_out = a.out or os.path.join(proj, f"{safe}_montage.mp4")

    todo = [a.only] if a.only else STAGES[STAGES.index(a.start):]
    log(f"pipeline PLAN THEYO: {' -> '.join(todo)}  (work={work})")
    t0 = time.time()
    tone = a.tone
    rcfg = load_config(work).get("review", {})
    has_gemini_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    gemini_on = rcfg.get("gemini_enabled", True) and has_gemini_key

    if "transcribe" in todo:
        sh("transcribe.py", a.video, work, "--model", a.model, "--lang", a.lang)
    if "brief" in todo:
        # LES YEUX AVANT (plan theyo 1bis) : Gemini voit la video brute en entier.
        if gemini_on:
            code, _ = sh("gemini_brief.py", a.video, work,
                         "--model", rcfg.get("gemini_model", "gemini-2.5-flash"),
                         tolerate=(1, 2))
            if code != 0:
                log("brief Gemini indisponible -> le monteur travaille sans (fallback frames).")
        else:
            log("brief Gemini saute (pas de cle ou review.gemini_enabled=false).")
    if "plan" in todo:
        sh("plan.py", work)
    if "auto" in todo and not a.no_overlays:
        # detection du ton + placement automatique des animations (PROPOSITION triable)
        sh("suggest_overlays.py", work, "--tone", tone)
        t = promote_overlays(work, a.force_overlays)
        if t:
            tone = t if a.tone == "auto" else a.tone
    if "cut" in todo:
        sh("build_cut.py", work)
    if "render" in todo:
        sh("render.py", work, render_out)
    elif not os.path.exists(render_out):
        # reprise sans render : reutiliser un rendu existant (final deja la, sinon work)
        render_out = final_out if os.path.exists(final_out) else render_out

    if not os.path.exists(render_out):
        die(f"aucun rendu a traiter ({render_out}). Lance sans --only/--from, ou --from render.")

    # VOIX EN AVANT (oreilles -> mains) : si la voix ne ressort pas du fond (jeu/musique
    # source), separation Demucs + remix voix boostee. Decision par MESURE, pas au feeling.
    acfg = load_config(work).get("audio", {})
    if "music" in todo and acfg.get("voice_up", "auto") != False:
        mode = acfg.get("voice_up", "auto")
        need = mode is True or mode == "on"
        if mode == "auto":
            code, out_txt = sh("ears.py", render_out, "--work", work, "--mix-only",
                               capture=True, tolerate=(1, 2))
            med = None
            for line in out_txt.splitlines():
                if line.startswith("MEDIAN_SNR_DB="):
                    med = float(line.split("=", 1)[1])
            if med is not None:
                need = med < acfg.get("min_snr_db", 6.0)
                log(f"oreilles : voix/fond median {med:+.1f} dB "
                    f"({'NOYEE -> voice_up' if need else 'OK'}).")
        if need:
            vu = os.path.join(work, f"{safe}_voiceup.mp4")
            code, _ = sh("voice_up.py", render_out, "--out", vu,
                         "--voice-gain", str(acfg.get("voice_gain_db", 5)),
                         "--bed-gain", str(acfg.get("bed_gain_db", -6)), tolerate=(1,))
            if code == 0 and os.path.exists(vu):
                render_out = vu
            else:
                log("voice_up indisponible (demucs ?) -> mix d'origine conserve.")

    if "music" in todo and not a.no_music:
        sug = os.path.join(work, "overlays.suggested.json")
        if os.path.exists(sug):
            tone = load_json(sug).get("_tone", tone)
        mood = "upbeat" if tone == "fun" else "corporate"
        # jamais lire+ecrire le meme fichier : passer par un temporaire si besoin
        music_in = render_out
        if os.path.abspath(music_in) == os.path.abspath(final_out):
            music_in = os.path.join(work, f"{safe}_premusic.mp4")
            shutil.copy(render_out, music_in)
        try:
            sh("add_music.py", music_in, mood, "--out", final_out, "--gain", "-20")
        except SystemExit:
            log("musique ignoree (echec) -> livraison sans musique.")
            if os.path.abspath(render_out) != os.path.abspath(final_out):
                shutil.copy(render_out, final_out)
    elif os.path.abspath(render_out) != os.path.abspath(final_out):
        shutil.copy(render_out, final_out)

    # LES YEUX APRES (plan theyo etapes 5-6) : sur le fichier REELLEMENT LIVRE (musique
    # comprise). Frames ciblees toujours ; verdict Gemini PREPONDERANT si cle.
    verdict_line = "review non lancee (--no-review)."
    if "review" in todo and not a.no_review:
        sh("review.py", final_out, "--frames", str(rcfg.get("sample_frames", 9)),
           "--out", os.path.join(work, "review"), "--targets", work, tolerate=(1,))
        log(f"frames de review -> {os.path.join(work, 'review')} (a REGARDER).")
        if gemini_on:
            code, _ = sh("gemini_review.py", final_out, "--work", work, tolerate=(2, 3))
            hist_path = os.path.join(work, "review_history.json")
            note = None
            if os.path.exists(hist_path):
                h = load_json(hist_path)
                note = h[-1].get("note") if h else None
            if code == 0 and note is not None:
                verdict_line = f"VERDICT GEMINI: {note:g}/10 -> VALIDE (seuil {rcfg.get('min_note', 7)})."
            elif code == 3:
                verdict_line = (f"VERDICT GEMINI: {note if note is not None else '?'}/10 -> NON LIVRABLE. "
                                f"Corrections OBLIGATOIRES (review_history.json) puis run.py --from cut|render.")
            else:
                verdict_line = "review Gemini indisponible -> juger les frames de work/review/ a l'oeil."
        else:
            verdict_line = "pas de cle Gemini : juger les frames de work/review/ a l'oeil (fallback)."
        log(verdict_line)

    # Livraison MINIMALE et stricte (regle utilisateur) : uniquement le montage, la
    # miniature, et shorts/ si des shorts existent. brief/DECISIONS/verdicts restent
    # dans work/<nom>/ (matiere de travail pour l'etape 9, jamais dans livraisons/).
    stats = load_json(os.path.join(work, "plan.json")).get("stats", {}) if \
        os.path.exists(os.path.join(work, "plan.json")) else {}
    log(f"stats: {stats}")
    log(f"TERMINE en {int(time.time()-t0)}s")
    log(f"LIVRAISON RANGEE -> {proj}")


if __name__ == "__main__":
    main()
