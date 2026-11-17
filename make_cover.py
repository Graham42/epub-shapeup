#!/usr/bin/env python3
"""Make cover.jpg (1600x2400) from the title block of https://basecamp.com/shapeup.

Chrome renders the live page so the site's own web font is used. The sketch, title, subtitle and
byline are cropped out and placed on a portrait canvas, with the Basecamp logo from the official
PDF title page at the bottom.

Needs: google-chrome, pdftoppm (poppler-utils), Pillow. Usage: python3 make_cover.py [cover.jpg]
"""
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

W, H = 1600, 2400
MARGIN = 150
SCALE = 4  # Chrome device scale factor
VIEW_W, VIEW_H = 800, 700  # CSS pixels; this width gives the stacked (sketch over title) layout


def dark_rows(img: Image.Image, threshold: int = 200) -> list[float]:
    """Longest unbroken run of dark pixels in each row, as a fraction of the width."""
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    out = []
    for y in range(h):
        best = run = 0
        for x in range(w):
            run = run + 1 if px[x, y] < threshold else 0
            best = max(best, run)
        out.append(best / w)
    return out


def segments(fractions: list[float]) -> list[tuple[int, int, float]]:
    """Runs of rows containing ink: (start, end, peak dark fraction)."""
    out, start, peak = [], None, 0.0
    for y, f in enumerate(fractions + [0.0]):
        if f > 0 and start is None:
            start, peak = y, f
        elif f > 0:
            peak = max(peak, f)
        elif start is not None:
            out.append((start, y, peak))
            start = None
    return out


def title_block(tmp: Path) -> Image.Image:
    shot = tmp / "page.png"
    subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={SCALE}", "--virtual-time-budget=8000",
                    f"--window-size={VIEW_W},{VIEW_H}", f"--screenshot={shot}", "https://basecamp.com/shapeup"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    page = Image.open(shot).convert("RGB")
    # The "← Basecamp.com" link sits left of the content column; keep only the column.
    col = page.crop((int(page.width * 0.32), 0, page.width, page.height))
    segs = segments(dark_rows(col))
    # Buttons are solid dark pills (long unbroken dark rows); the first one ends the title block.
    end = next(s for s, _, peak in segs if peak > 0.2)
    top = segs[0][0]
    bottom = max(e for s, e, _ in segs if e <= end)
    block = col.crop((0, top, col.width, bottom))
    return block.crop(ImageOps.invert(block.convert("L")).getbbox())


def basecamp_logo(tmp: Path) -> Image.Image:
    pdf = tmp / "shape-up.pdf"
    req = urllib.request.Request("https://basecamp.com/shapeup/shape-up.pdf", headers={"User-Agent": "Mozilla/5.0"})
    pdf.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-scale-to-x", str(W), "-scale-to-y", str(H),
                    "-png", str(pdf), str(tmp / "title")], check=True, stderr=subprocess.DEVNULL)
    title = Image.open(tmp / "title.png").convert("RGB")
    segs = segments(dark_rows(title))
    s, e, _ = segs[-1]  # the logo is the last ink on the page
    strip = title.crop((0, s, W, e))
    return strip.crop(ImageOps.invert(strip.convert("L")).getbbox())


def main(out: str) -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        block, logo = title_block(tmp), basecamp_logo(tmp)
    scale = (W - 2 * MARGIN) / block.width
    block = block.resize((W - 2 * MARGIN, round(block.height * scale)), Image.LANCZOS)
    cover = Image.new("RGB", (W, H), "white")
    cover.paste(block, (MARGIN, round(H * 0.16)))
    cover.paste(logo, ((W - logo.width) // 2, H - MARGIN - logo.height))
    cover.save(out, quality=95)
    print(f"wrote {out} ({W}x{H})", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cover.jpg")
