#!/usr/bin/env python3
"""
create_demo_library.py — Generates a demo image library for screenshots.

Creates a realistic folder structure with:
  - Exact duplicates (identical bytes, different names/locations)
  - Visual duplicates (same image, different resolution or compression)
  - Unique images (no duplicates)

Usage:
    python create_demo_library.py [output_dir]
    python create_demo_library.py demo_images
"""

import io
import os
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)


OUTPUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo_images")

# ── Colour palettes for the demo images ──────────────────────────────────────
SCENES = [
    {
        "name": "sunset",
        "label": "Sunset",
        "bg": (220, 100, 40),
        "sun": (255, 230, 80),
        "sky": [(255, 160, 60), (200, 80, 30), (120, 40, 60)],
    },
    {
        "name": "forest",
        "label": "Forest",
        "bg": (30, 100, 40),
        "sun": (180, 220, 80),
        "sky": [(60, 160, 60), (30, 100, 40), (20, 60, 20)],
    },
    {
        "name": "ocean",
        "label": "Ocean",
        "bg": (30, 80, 180),
        "sun": (240, 240, 255),
        "sky": [(80, 140, 220), (40, 100, 200), (20, 60, 160)],
    },
    {
        "name": "mountain",
        "label": "Mountain",
        "bg": (100, 100, 140),
        "sun": (255, 255, 200),
        "sky": [(160, 180, 220), (100, 120, 160), (60, 70, 100)],
    },
    {
        "name": "desert",
        "label": "Desert",
        "bg": (210, 170, 80),
        "sun": (255, 240, 100),
        "sky": [(240, 200, 100), (210, 160, 60), (170, 110, 40)],
    },
    {
        "name": "city",
        "label": "City",
        "bg": (60, 60, 80),
        "sun": (200, 200, 255),
        "sky": [(100, 100, 140), (70, 70, 100), (40, 40, 60)],
    },
]


def draw_scene(scene: dict, width: int = 800, height: int = 600) -> Image.Image:
    """Draws a simple coloured landscape scene."""
    img = Image.new("RGB", (width, height), scene["bg"])
    draw = ImageDraw.Draw(img)

    sky = scene["sky"]

    # Sky gradient (3 bands up to the horizon)
    horizon = height // 2
    band = horizon // 3
    draw.rectangle([0, 0, width, band], fill=sky[0])
    draw.rectangle([0, band, width, band * 2], fill=sky[1])
    draw.rectangle([0, band * 2, width, horizon], fill=sky[2])

    # Ground
    draw.rectangle([0, height // 2, width, height], fill=scene["bg"])

    # Sun / moon
    sx, sy = int(width * 0.75), int(height * 0.2)
    r = int(width * 0.06)
    draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=scene["sun"])

    # Simple silhouette (triangle hill)
    cx = width // 2
    draw.polygon(
        [(cx - 180, height // 2), (cx, int(height * 0.25)), (cx + 180, height // 2)],
        fill=scene["bg"],
    )

    # Label
    draw.text((16, 16), scene["label"], fill=(255, 255, 255, 200))

    return img


def save_jpeg(img: Image.Image, path: Path, quality: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def make_resized(img: Image.Image, scale: float) -> Image.Image:
    w, h = img.size
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def make_compressed(img: Image.Image, quality: int) -> Image.Image:
    """Re-saves at low quality to JPEG and reloads (simulates camera re-export)."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).copy()


def make_slightly_cropped(img: Image.Image, pixels: int = 20) -> Image.Image:
    w, h = img.size
    return img.crop((pixels, pixels, w - pixels, h - pixels)).resize((w, h), Image.LANCZOS)


# ── Build the demo library ────────────────────────────────────────────────────

def build(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)

    print(f"Creating demo library in: {root.resolve()}")

    # ── Folder layout ──────────────────────────────────────────────────────
    # root/
    #   photos/           ← originals (unique images)
    #   photos/trip/      ← subfolder with some originals
    #   backup/           ← exact copies of selected photos (exact duplicates)
    #   exports/          ← re-exported / resized versions (visual duplicates)
    #   misc/             ← unrelated unique images

    photos   = root / "photos"
    trip     = root / "photos" / "trip"
    backup   = root / "backup"
    exports  = root / "exports"
    misc     = root / "misc"

    for d in [photos, trip, backup, exports, misc]:
        d.mkdir(parents=True, exist_ok=True)

    originals = {}  # scene_name → PIL Image

    # ── 1. Create originals ────────────────────────────────────────────────
    for scene in SCENES:
        img = draw_scene(scene)
        originals[scene["name"]] = img

    # photos/ — first 4 scenes
    for scene in SCENES[:4]:
        path = photos / f"{scene['name']}.jpg"
        save_jpeg(originals[scene["name"]], path, quality=92)
        print(f"  [unique]         {path.relative_to(root)}")

    # photos/trip/ — last 2 scenes
    for scene in SCENES[4:]:
        path = trip / f"{scene['name']}.jpg"
        save_jpeg(originals[scene["name"]], path, quality=92)
        print(f"  [unique]         {path.relative_to(root)}")

    # ── 2. Exact duplicates in backup/ ────────────────────────────────────
    # Copy 3 originals byte-for-byte into backup/
    exact_dupes = ["sunset", "forest", "ocean"]
    for name in exact_dupes:
        src = photos / f"{name}.jpg"
        dst = backup / f"{name}_backup.jpg"
        shutil.copy2(src, dst)
        print(f"  [exact duplicate] {dst.relative_to(root)}  ←→  photos/{name}.jpg")

    # Also nest one in a sub-backup folder
    nested = backup / "old"
    nested.mkdir(exist_ok=True)
    shutil.copy2(photos / "mountain.jpg", nested / "mountain_copy.jpg")
    print(f"  [exact duplicate] backup/old/mountain_copy.jpg  ←→  photos/mountain.jpg")

    # ── 3. Visual duplicates in exports/ ─────────────────────────────────
    # a) Resized versions (e.g. web thumbnail, mobile export)
    for name, scale, label in [
        ("sunset",   0.5,  "sunset_web.jpg"),
        ("forest",   0.75, "forest_medium.jpg"),
        ("mountain", 2.0,  "mountain_4k.jpg"),
    ]:
        img_resized = make_resized(originals[name], scale)
        path = exports / label
        save_jpeg(img_resized, path, quality=88)
        print(f"  [visual duplicate] {path.relative_to(root)}  (resized {scale}x)")

    # b) Recompressed versions (same image, lower quality)
    for name, quality, label in [
        ("ocean",   60, "ocean_compressed.jpg"),
        ("city",    70, "city_lowquality.jpg"),
    ]:
        img_src = originals[name]
        # For city, get the original from trip/
        if name == "city":
            img_src = originals[name]
        img_comp = make_compressed(img_src, quality)
        path = exports / label
        save_jpeg(img_comp, path, quality=quality)
        src_folder = "photos/trip" if name in ["desert", "city"] else "photos"
        print(f"  [visual duplicate] {path.relative_to(root)}  (recompressed q={quality})")

    # c) Slightly cropped (simulate "edited" version)
    img_cropped = make_slightly_cropped(originals["sunset"], pixels=30)
    path = exports / "sunset_edited.jpg"
    save_jpeg(img_cropped, path, quality=90)
    print(f"  [visual duplicate] {path.relative_to(root)}  (cropped/edited)")

    # d) PNG version of a JPEG (same content, different format)
    path_png = exports / "forest_original.png"
    save_png(originals["forest"], path_png)
    print(f"  [visual duplicate] {path.relative_to(root)}  (PNG of forest.jpg)")

    # ── 4. Misc unique images ─────────────────────────────────────────────
    extra_scenes = [
        {"name": "aurora",   "label": "Aurora",   "bg": (20, 60, 80),   "sun": (100, 255, 180), "sky": [(30, 120, 100), (20, 80, 60), (10, 40, 30)]},
        {"name": "volcano",  "label": "Volcano",  "bg": (140, 40, 10),  "sun": (255, 180, 40),  "sky": [(200, 80, 20), (150, 40, 10), (100, 20, 5)]},
        {"name": "tundra",   "label": "Tundra",   "bg": (180, 200, 220),"sun": (255, 255, 240), "sky": [(220, 230, 240), (190, 210, 225), (160, 180, 200)]},
    ]
    for scene in extra_scenes:
        img = draw_scene(scene)
        path = misc / f"{scene['name']}.jpg"
        save_jpeg(img, path, quality=91)
        print(f"  [unique]         {path.relative_to(root)}")

    # ── Summary ───────────────────────────────────────────────────────────
    all_files = list(root.rglob("*.jpg")) + list(root.rglob("*.png"))
    print(f"\nDone. {len(all_files)} images in {root.resolve()}")
    print("""
Structure:
  photos/          — 4 unique originals
  photos/trip/     — 2 unique originals
  backup/          — 3 exact duplicates + 1 nested exact duplicate
  exports/         — 6 visual duplicates (resized, recompressed, cropped, PNG)
  misc/            — 3 unrelated unique images

Run MediaDedupe on this folder to see the results.
""")


if __name__ == "__main__":
    build(OUTPUT_DIR)
