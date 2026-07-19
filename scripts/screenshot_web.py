"""B-roll par SCREENSHOT WEB (pages, articles, sites) via Playwright.
Capture une URL et l'enregistre dans remotion/public/media/ pour un overlay image.

Usage:
  python screenshot_web.py "https://exemple.com/article" --name article --full
  python screenshot_web.py "https://x.com/..." --name tweet --w 1200 --h 800
Imprime le nom de fichier (a utiliser comme "src" d'un overlay image).
"""
import argparse
import os
import sys
from common import FFMPEG, ROOT, run, log

MEDIA = os.path.join(ROOT, "remotion", "public", "media")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--name", required=True)
    ap.add_argument("--w", type=int, default=1280)
    ap.add_argument("--h", type=int, default=800)
    ap.add_argument("--full", action="store_true", help="page entiere (sinon viewport)")
    ap.add_argument("--wait", type=int, default=2500, help="ms d'attente apres chargement")
    a = ap.parse_args()
    os.makedirs(MEDIA, exist_ok=True)
    png = os.path.join(MEDIA, f"{a.name}.png")
    jpg = os.path.join(MEDIA, f"{a.name}.jpg")

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        log("Playwright absent : pip install playwright && python -m playwright install chromium")
        sys.exit(2)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": a.w, "height": a.h}, device_scale_factor=2)
        try:
            page.goto(a.url, wait_until="networkidle", timeout=45000)
        except Exception as e:
            log(f"chargement partiel: {str(e)[:100]}")
        # accepte/ferme les bandeaux cookies courants (best-effort)
        for sel in ["text=Tout accepter", "text=Accepter", "text=Accept all", "#onetrust-accept-btn-handler"]:
            try:
                page.click(sel, timeout=1200)
                break
            except Exception:
                pass
        page.wait_for_timeout(a.wait)
        page.screenshot(path=png, full_page=a.full)
        browser.close()

    # normalise en jpg propre
    run([FFMPEG, "-y", "-i", png, "-frames:v", "1", "-q:v", "3", jpg])
    if os.path.exists(png):
        os.remove(png)
    log(f"screenshot: {a.name}.jpg")
    print(f"{a.name}.jpg")


if __name__ == "__main__":
    main()
