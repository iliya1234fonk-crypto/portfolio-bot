from PIL import Image, ImageDraw, ImageFont
import os
import math

FONT = "/tmp/Onest.ttf"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"
OUT = "/storage/emulated/0/Download/portfolio-bot"
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

DARK_TOP = (11, 14, 19)
DARK_BOT = (20, 26, 34)
GRID = (24, 30, 38)
WHITE = (246, 248, 250)
MUTED = (138, 148, 166)

W, H = 720, 480


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def bg():
    strip = Image.new("RGB", (1, H))
    d = ImageDraw.Draw(strip)
    for y in range(H):
        d.point((0, y), fill=lerp(DARK_TOP, DARK_BOT, y / (H - 1)))
    img = strip.resize((W, H), Image.BILINEAR)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=GRID, width=1)
    return img


# ---------- мотивы ----------
def m_arrow(d, t, acc):
    y = 240
    d.rounded_rectangle([596, 176, 690, 304], radius=16, outline=acc, width=4)
    x1 = 480 + (596 - 480) * min(1, t * 1.2)
    d.line([(470, y), (x1, y)], fill=acc, width=9)
    d.polygon([(x1, y - 15), (x1 + 22, y), (x1, y + 15)], fill=acc)


def m_cal(d, t, acc):
    s, gap, ox, oy = 52, 10, 505, 148
    for i in range(3):
        for j in range(3):
            idx = i * 3 + j
            x = ox + j * (s + gap)
            y = oy + i * (s + gap)
            if (idx + 1) / 9 <= t:
                d.rounded_rectangle([x, y, x + s, y + s], radius=10, fill=acc)
            else:
                d.rounded_rectangle([x, y, x + s, y + s], radius=10, outline=(60, 70, 84), width=3)


def m_win(d, t, acc):
    d.rounded_rectangle([478, 138, 700, 342], radius=16, outline=acc, width=4)
    d.line([(478, 184), (700, 184)], fill=acc, width=3)
    for k in range(3):
        d.ellipse([494 + k * 22, 155, 506 + k * 22, 167], fill=acc)
    widths = [0.92, 0.6, 0.75]
    for k, w in enumerate(widths):
        prog = min(1, max(0, (t - k * 0.18) / 0.5))
        if prog > 0:
            y = 212 + k * 38
            d.rounded_rectangle([502, y, 502 + 172 * w * prog, y + 16], radius=8, fill=acc)


QR = [(i, j) for i in range(5) for j in range(5)
      if not ((i <= 1 and j <= 1) or (i <= 1 and j >= 3) or (i >= 3 and j <= 1))]
QR = [c for k, c in enumerate(QR) if (k * 7 + c[0] * 5 + c[1]) % 4 != 0]


def m_qr(d, t, acc):
    size, gap, ox, oy = 26, 6, 512, 150
    step = size + gap

    def finder(x, y):
        d.rectangle([x, y, x + 62, y + 62], outline=acc, width=6)
        d.rectangle([x + 20, y + 20, x + 42, y + 42], fill=acc)

    finder(ox, oy)
    finder(ox + 4 * step, oy)
    finder(ox, oy + 4 * step)

    for idx, (i, j) in enumerate(QR):
        if (idx + 1) / len(QR) <= t:
            x = ox + j * step
            y = oy + i * step
            d.rectangle([x, y, x + size, y + size], fill=acc)


def m_spark(d, t, acc):
    cx, cy = 590, 240
    for k in range(8):
        ang = math.radians(k * 45 + t * 30)
        r0 = 26
        r1 = 26 + (74 * min(1, t * 1.3)) * (0.55 + 0.45 * ((k % 3) / 2))
        d.line(
            [
                (cx + math.cos(ang) * r0, cy + math.sin(ang) * r0),
                (cx + math.cos(ang) * r1, cy + math.sin(ang) * r1),
            ],
            fill=acc,
            width=9,
        )
    d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=acc)


def m_pencil(d, t, acc):
    x0, y0, x1, y1 = 486, 306, 686, 172
    xe = x0 + (x1 - x0) * min(1, t)
    ye = y0 + (y1 - y0) * min(1, t)
    d.line([(x0, y0), (xe, ye)], fill=acc, width=11)
    d.polygon([(xe, ye - 18), (xe + 24, ye + 4), (xe - 16, ye + 18)], fill=acc)


MOTIFS = {
    "arrow": m_arrow,
    "cal": m_cal,
    "win": m_win,
    "qr": m_qr,
    "spark": m_spark,
    "pencil": m_pencil,
}


def wrap(title, fnt, d, maxw):
    words = title.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textbbox((0, 0), test, font=fnt)[2] <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_card(name, title, price, motif, accent):
    base = bg()
    f_tag = font(22, 600)
    f_title = font(52, 800)
    f_price = font(34, 700)

    frames = []
    steps = 12
    for i in range(steps + 1):
        t = i / steps
        fr = base.copy()
        d = ImageDraw.Draw(fr)

        d.text((56, 46), "УСЛУГА", font=f_tag, fill=accent)
        d.rectangle([56, 78, 152, 81], fill=accent)

        lines = wrap(title, f_title, d, 400)
        y = 150
        for ln in lines[:2]:
            d.text((54, y), ln, font=f_title, fill=WHITE)
            y += 62

        d.rounded_rectangle([56, 380, 300, 436], radius=28, fill=(28, 36, 46), outline=accent, width=2)
        d.text((80, 393), price, font=f_price, fill=accent)

        MOTIFS[motif](d, t, accent)
        frames.append(fr)

    for _ in range(2):
        frames.append(frames[-1])

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    durations = [70] * (len(pal) - 1) + [2200]
    path = os.path.join(ASSETS, name)
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    pal[-1].save(os.path.join(OUT, name.replace(".gif", "-preview.png")))
    return path, os.path.getsize(path) // 1024


CARDS = [
    ("svc_zayavki.gif", "Бот приёма заявок", "750 ₽", "arrow", (182, 255, 62)),
    ("svc_zapis.gif", "Бот записи", "1 250 ₽", "cal", (76, 215, 240)),
    ("svc_site.gif", "Сайт-визитка", "500 ₽", "win", (255, 138, 61)),
    ("svc_menu.gif", "Меню по QR", "750 ₽", "qr", (61, 224, 160)),
    ("svc_ai.gif", "ИИ-бот", "2 000 ₽", "spark", (106, 168, 255)),
    ("svc_custom.gif", "Свой вариант", "по задаче", "pencil", (222, 228, 238)),
]

if __name__ == "__main__":
    for name, title, price, motif, acc in CARDS:
        p, kb = make_card(name, title, price, motif, acc)
        print(name, kb, "KB")
