"""Generate a high-res PNG app icon for iOS home-screen (apple-touch-icon)."""
from PIL import Image, ImageDraw
from pathlib import Path

OUT_DIR = Path(r"d:\Documents\lifemanager\static")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 512
RADIUS = int(SIZE * 0.22)  # iOS rounds corners itself, but keep a subtle base


def make_gradient(size, top, bottom):
    img = Image.new("RGB", (size, size), top)
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


# iOS masks the icon into a squircle, so paint a full-bleed background.
bg = make_gradient(SIZE, (250, 250, 252), (232, 234, 240))
canvas = bg.convert("RGBA")
draw = ImageDraw.Draw(canvas)

cx, cy = SIZE // 2, SIZE // 2
r_outer = int(SIZE * 0.28)
r_inner = int(SIZE * 0.14)

outer_pts = [(cx, cy - r_outer), (cx + r_outer, cy), (cx, cy + r_outer), (cx - r_outer, cy)]
draw.polygon(outer_pts, fill=(28, 30, 36, 255))

inner_pts = [(cx, cy - r_inner), (cx + r_inner, cy), (cx, cy + r_inner), (cx - r_inner, cy)]
draw.polygon(inner_pts, fill=(245, 246, 250, 255))

# apple-touch-icon: 180x180 is the modern iPad/iPhone size; ship 180 + 512.
canvas.save(OUT_DIR / "app-icon-512.png", format="PNG")
canvas.resize((180, 180), Image.LANCZOS).save(OUT_DIR / "apple-touch-icon.png", format="PNG")
print("Saved:", OUT_DIR / "apple-touch-icon.png", "and app-icon-512.png")
