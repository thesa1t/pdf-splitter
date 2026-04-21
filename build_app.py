"""Генерация иконок: icon.png → icon.icns (macOS), icon.ico (Windows).

Запускается автоматически из build_macos.sh / build_windows.bat.
"""

import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ICON_SIZE = 512
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def create_png() -> str:
    """Генерирует icon.png, если его нет."""
    png_path = os.path.join(SCRIPT_DIR, "icon.png")
    if os.path.isfile(png_path):
        return png_path

    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 20
    draw.rounded_rectangle(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        radius=60, fill=(41, 98, 255),
    )
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 140)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((ICON_SIZE // 2, ICON_SIZE // 2 - 40), "PDF",
              fill="white", font=font, anchor="mm")
    y = ICON_SIZE // 2 + 60
    draw.line([(margin + 60, y), (ICON_SIZE - margin - 60, y)],
              fill=(255, 255, 255, 180), width=6)
    arrow_y = y + 40
    for ax in (ICON_SIZE // 3, 2 * ICON_SIZE // 3):
        draw.polygon(
            [(ax - 25, arrow_y), (ax + 25, arrow_y), (ax, arrow_y + 35)],
            fill="white",
        )
    img.save(png_path)
    return png_path


def create_ico(png_path: str) -> str:
    """Кроссплатформенная генерация .ico из .png."""
    ico_path = os.path.join(SCRIPT_DIR, "icon.ico")
    img = Image.open(png_path).convert("RGBA")
    img.save(
        ico_path, format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return ico_path


def create_icns(png_path: str) -> str | None:
    """Генерирует .icns на macOS через iconutil (самый надёжный способ)."""
    icns_path = os.path.join(SCRIPT_DIR, "icon.icns")
    if sys.platform != "darwin":
        return icns_path if os.path.isfile(icns_path) else None

    iconset = os.path.join(SCRIPT_DIR, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    base = Image.open(png_path).convert("RGBA")
    for size, name in [
        (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
    ]:
        base.resize((size, size), Image.LANCZOS).save(os.path.join(iconset, name))
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", iconset, "-o", icns_path],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.run(
            ["sips", "-s", "format", "icns", png_path, "--out", icns_path],
            check=False, capture_output=True,
        )
    finally:
        import shutil
        shutil.rmtree(iconset, ignore_errors=True)
    return icns_path if os.path.isfile(icns_path) else None


def main():
    png = create_png()
    print(f"PNG: {png}")
    ico = create_ico(png)
    print(f"ICO: {ico}")
    icns = create_icns(png)
    print(f"ICNS: {icns}")


if __name__ == "__main__":
    main()
