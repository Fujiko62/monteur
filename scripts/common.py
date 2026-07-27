"""Utilitaires partages du monteur : detection ffmpeg, config, ffprobe, logs."""
import json
import os
import subprocess
import sys
import shutil
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Console Windows = cp1252 : un emoji dans un log ferait crasher print(). UTF-8 force.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_name(path_or_name):
    """Nom de projet propre a partir d'un chemin video ou d'un nom (sans espaces/accents)."""
    import re as _re
    base = os.path.splitext(os.path.basename(path_or_name))[0]
    n = _re.sub(r"[^\w-]+", "_", base).strip("_")
    return n or "video"


def project_dir(name):
    """Dossier de LIVRAISON d'une video : livraisons/<nom>/. Contenu minimal et strict :
    <nom>.mp4 + miniature.png + shorts/ (UNIQUEMENT si des shorts existent — pas cree
    ici a l'avance, make_short.py le cree au premier short reel). Une video = un dossier,
    rien de plus (pas de brief/props/docs : ca reste dans work/<nom>/)."""
    d = os.path.join(ROOT, "livraisons", safe_name(name))
    os.makedirs(d, exist_ok=True)
    return d


def apply_caption_preset(capcfg):
    """Presets de style sous-titres. `preset` dans config.captions :
    - "viral" (defaut historique) : MAJUSCULES, boite jaune, contour noir epais.
    - "clean" (ref. shorts pro) : minuscules, plus petit, halo sombre doux (glow),
      mot actif lumineux — premium, discret, tres lisible.
    Les cles explicitement definies par l'utilisateur ne sont PAS ecrasees
    (le preset ne touche que ce qui reste aux valeurs 'viral' par defaut)."""
    preset = capcfg.get("preset", "viral")
    if preset != "clean":
        return capcfg
    defaults = {
        "uppercase": False,
        "highlight_mode": "glow",
        "font_size_ratio": round(capcfg.get("font_size_ratio", 0.056) * 0.72, 4),
        "max_words_per_line": 3,
        "pop_scale": 1.04,
        "stroke_width_ratio": 0.0,
    }
    marker = capcfg.get("_user_keys", [])
    for k, v in defaults.items():
        if k not in marker:
            capcfg[k] = v
    return capcfg


def load_dotenv():
    """Charge ROOT/.env dans os.environ (sans ecraser des variables deja definies)."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_dotenv()


def gemini_keys():
    """Toutes les cles Gemini disponibles (plusieurs comptes = plusieurs quotas).
    GEMINI_API_KEY = cle principale. GEMINI_API_KEY_2, _3... = cles de secours
    (autre compte Google), utilisees automatiquement quand la precedente est a quota."""
    keys = []
    if os.environ.get("GEMINI_API_KEY"):
        keys.append(os.environ["GEMINI_API_KEY"])
    i = 2
    while os.environ.get(f"GEMINI_API_KEY_{i}"):
        keys.append(os.environ[f"GEMINI_API_KEY_{i}"])
        i += 1
    return keys


def gemini_client_cycle():
    """Genere un client google-genai par cle dispo, dans l'ordre. A chaque cle a plat
    (429/quota), l'appelant passe a next(cycle) pour retenter avec la cle suivante."""
    from google import genai
    for key in gemini_keys():
        yield genai.Client(api_key=key)


def is_quota_error(exc):
    s = str(exc).lower()
    return "429" in s or "quota" in s or "resource_exhausted" in s or "rate limit" in s


def gemini_generate(model, build_contents, config, retries_per_key=3):
    """Appelle Gemini en essayant CHAQUE cle dispo (gemini_keys()), et sur chaque cle
    retente `retries_per_key` fois. Bascule de cle des qu'une erreur de quota (429)
    est detectee -> une 2e cle (autre compte Google) reprend la main automatiquement.
    `build_contents(client)` : fabrique la liste `contents` (utile pour re-uploader un
    fichier avec le client courant, l'upload d'une cle n'etant pas valide sur une autre).
    Retourne le texte de la reponse. Leve la derniere erreur si toutes les cles echouent."""
    keys = gemini_keys()
    if not keys:
        raise RuntimeError("aucune cle Gemini (.env: GEMINI_API_KEY / GEMINI_API_KEY_2...)")
    from google import genai
    last = None
    for ki, key in enumerate(keys, 1):
        client = genai.Client(api_key=key)
        for attempt in range(retries_per_key):
            try:
                contents = build_contents(client)
                r = client.models.generate_content(model=model, contents=contents, config=config)
                return r.text
            except Exception as e:  # noqa: BLE001
                last = e
                if is_quota_error(e):
                    log(f"cle Gemini #{ki} a quota -> {'nouvelle tentative' if attempt < retries_per_key - 1 else 'cle suivante'}")
                    if len(keys) > 1:
                        break  # passe direct a la cle suivante, inutile de reessayer la meme
    raise last


def log(msg):
    print(f"[monteur] {msg}", flush=True)


def die(msg, code=1):
    print(f"[monteur][ERREUR] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def find_ffmpeg():
    """Retourne (ffmpeg, ffprobe) en cherchant PATH puis les paquets WinGet."""
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for pat in patterns:
        hits = glob.glob(pat, recursive=True)
        if hits:
            b = os.path.dirname(hits[0])
            return os.path.join(b, "ffmpeg.exe"), os.path.join(b, "ffprobe.exe")
    die("ffmpeg introuvable. Installe-le : winget install Gyan.FFmpeg")


FFMPEG, FFPROBE = find_ffmpeg()


def run(cmd, **kw):
    """Execute une commande, remonte stderr en cas d'echec."""
    kw.setdefault("check", True)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, **kw)
    except subprocess.CalledProcessError as e:
        die(f"commande echouee: {' '.join(str(c) for c in cmd)}\n{e.stderr}")


def ffprobe_info(path):
    """Retourne dict : width, height, fps, duration, has_audio."""
    r = run([FFPROBE, "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", path])
    data = json.loads(r.stdout)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        die(f"pas de flux video dans {path}")
    num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
    fps = float(num) / float(den or 1)
    dur = float(data["format"].get("duration") or v.get("duration") or 0)
    return {
        "width": int(v["width"]),
        "height": int(v["height"]),
        "fps": round(fps, 3),
        "duration": dur,
        "has_audio": a is not None,
    }


def make_proxy(video, work_dir, name="proxy_review.mp4", max_mb=120):
    """Proxy 720p crf30 pour uploader a Gemini (erreur connue #7 : JAMAIS le master).
    Retourne le chemin a uploader (la video elle-meme si deja assez legere)."""
    size = os.path.getsize(video)
    if size < max_mb * 1024 * 1024:
        return video
    proxy = os.path.join(work_dir, name)
    if not os.path.exists(proxy) or os.path.getmtime(proxy) < os.path.getmtime(video):
        log(f"proxy 720p pour l'upload ({size//(1024*1024)} Mo -> compact)...")
        run([FFMPEG, "-y", "-i", video, "-vf", "scale=-2:720", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "96k", proxy])
    return proxy


def load_config(work_dir=None):
    """Charge config.json (racine) fusionnee avec un override eventuel dans work_dir.

    PIEGE VECU : un override place au mauvais endroit est ignore EN SILENCE (pas
    d'erreur, config par defaut utilisee) -> sous-titres a zero / couleur non voulue
    decouverts seulement a la verification visuelle, un build entier plus tard. D'ou
    le log explicite ci-dessous : le seul chemin valide est work_dir/config.override.json,
    et l'absence de ce fichier doit etre un CHOIX visible, jamais une surprise."""
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    if work_dir:
        ov = os.path.join(work_dir, "config.override.json")
        if os.path.exists(ov):
            _deep_merge(cfg, json.load(open(ov, encoding="utf-8")))
            log(f"config: override applique ({ov})")
        else:
            log(f"config: AUCUN override trouve a {ov} — config.json par defaut utilisee.")
    return cfg


def _deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def load_json(path):
    return json.load(open(path, encoding="utf-8"))
