"""PWA 아이콘 생성: 노란 바탕에 흰 별. 사용법: python scripts/make_icons.py public"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def star_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), "#f5b700")
    cx = cy = size / 2
    outer, inner = size * 0.30, size * 0.30 * 0.45  # maskable 안전 영역(가운데 80%) 안에 들어가게
    points = [
        (cx + (outer if i % 2 == 0 else inner) * math.sin(i * math.pi / 5),
         cy - (outer if i % 2 == 0 else inner) * math.cos(i * math.pi / 5))
        for i in range(10)
    ]
    ImageDraw.Draw(img).polygon(points, fill="white")
    return img


out = Path(sys.argv[1])
for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]:
    star_icon(size).save(out / name)
    print("wrote", out / name)
