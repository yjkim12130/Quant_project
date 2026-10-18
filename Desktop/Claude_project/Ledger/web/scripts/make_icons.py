"""PWA 아이콘 생성: 초록 바탕에 흰 막대그래프. 사용법: python scripts/make_icons.py public"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def chart_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), "#28a745")
    draw = ImageDraw.Draw(img)
    # maskable 안전 영역(가운데 80%) 안에 막대 3개
    left, bottom, bar, gap = size * 0.27, size * 0.70, size * 0.12, size * 0.06
    for i, height in enumerate([0.22, 0.38, 0.30]):
        x = left + i * (bar + gap)
        draw.rounded_rectangle([x, bottom - size * height, x + bar, bottom], radius=size * 0.02, fill="white")
    return img


out = Path(sys.argv[1])
for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]:
    chart_icon(size).save(out / name)
    print("wrote", out / name)
