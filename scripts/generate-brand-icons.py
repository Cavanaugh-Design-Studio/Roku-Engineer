"""Rebuild independent desktop icons from the checked-in 1024px master PNG."""
from pathlib import Path
import shutil
from PIL import Image

base = Path(__file__).resolve().parents[1] / "apps" / "roku-engineer-studio" / "assets"
source = Image.open(base / "engineer-mark.png").convert("RGBA")
source.save(base / "icon.ico", format="ICO", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
source.save(base / "icon.icns", format="ICNS")
shutil.copyfile(base / "engineer-mark.svg", base / "icon.svg")
for folder in ("ico-parts", "icon.iconset"):
    for output in (base / folder).glob("*.png"):
        with Image.open(output) as existing:
            size = existing.size
        source.resize(size, Image.Resampling.LANCZOS).save(output)
for name in ("icon.png", "icon-256.png"):
    source.resize((256, 256), Image.Resampling.LANCZOS).save(base / name)
print("PNG, multi-resolution ICO, and ICNS generated.")
