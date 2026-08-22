from pathlib import Path

from PIL import Image


root = Path(__file__).resolve().parents[1]
assets = root / "assets" / "images"
source = assets / "icon.png"
targets = [
    assets / "icon.png",
    assets / "splash-icon.png",
    assets / "favicon.png",
    assets / "android-icon-foreground.png",
]

with Image.open(source) as image:
    optimized = image.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    for target in targets:
        optimized.save(target, format="PNG", optimize=True, compress_level=9)

print("Optimized Synth Now icon assets to 512px PNG files.")
