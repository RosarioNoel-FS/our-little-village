"""Shrinks oversized photos in place (same name, same format) so uploads from a phone don't slow the site down.
Usage: python3 cms/optimize.py assets/work    (needs Pillow; the GitHub Action installs it)"""
import os, sys
from PIL import Image, ImageOps

MAX_SIDE, MAX_BYTES = 1400, 450_000


def shrink(path):
    if os.path.getsize(path) <= MAX_BYTES:
        with Image.open(path) as im:
            if max(im.size) <= MAX_SIDE:
                return False
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # phone photos store rotation in EXIF; bake it in before EXIF is dropped
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        fmt = {".png": "PNG", ".webp": "WEBP"}.get(os.path.splitext(path)[1].lower(), "JPEG")
        if fmt == "JPEG":
            im.convert("RGB").save(path, "JPEG", quality=82, optimize=True, progressive=True)
        elif fmt == "WEBP":
            im.save(path, "WEBP", quality=80)
        else:
            im.save(path, "PNG", optimize=True)
    return True


if __name__ == "__main__":
    folder = sys.argv[1]
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and shrink(os.path.join(folder, name)):
            print("shrank", name, os.path.getsize(os.path.join(folder, name)), "bytes")
