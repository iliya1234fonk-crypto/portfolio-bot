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


def rr(d, box, r, fill=None, outline=None, w=3):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


# ---------- мотивы ----------
def m_cards(d, t, acc):
    """каталог: карточки услуг выезжают стопкой"""
    x, y, w, h = 486, 132, 186, 46
    for i in range(4):
        p = min(1, max(0, (t - i * 0.14) / 0.35))
        if p <= 0:
            continue
        yy = y + i * 60
        xx = x + (1 - p) * 60
        rr(d, [xx, yy, xx + w, yy + h], 10, fill=(24, 31, 40), outline=(52, 62, 78), w=2)
        d.rounded_rectangle([xx + 12, yy + 13, xx + 32, yy + 33], radius=6, fill=acc)
        d.rounded_rectangle([xx + 44, yy + 15, xx + 44 + 90 * p, yy + 22], radius=4, fill=(70, 82, 100))
        d.rounded_rectangle([xx + 44, yy + 26, xx + 44 + 58 * p, yy + 32], radius=3, fill=(48, 58, 72))


def m_split(d, t, acc):
    """примеры: две рамки — боты и сайты"""
    for k, (bx, by) in enumerate([(486, 132), (596, 132)]):
        p = min(1, max(0, (t - k * 0.2) / 0.45))
        if p <= 0:
            continue
        x0, y0 = bx, by
        x1, y1 = bx + 100, by + 216
        col = acc if k == 0 else (255, 138, 61)
        rr(d, [x0, y0, x1, y1], 12, fill=(18, 23, 31), outline=col, w=3)
        if k == 0:
            # чат
            for i in range(2):
                d.rounded_rectangle([x0 + 12, y0 + 16 + i * 34, x0 + 12 + 64, y0 + 16 + i * 34 + 22],
                                    radius=8, fill=(34, 42, 54))
            d.rounded_rectangle([x0 + 26, y0 + 86, x0 + 88, y0 + 108], radius=8, fill=col)
            d.rounded_rectangle([x0 + 26, y0 + 116, x0 + 88, y0 + 138], radius=8, fill=(34, 42, 54))
        else:
            # окно
            d.rounded_rectangle([x0 + 12, y0 + 16, x1 - 12, y0 + 40], radius=6, fill=(34, 42, 54))
            for i in range(3):
                d.ellipse([x0 + 18 + i * 12, y0 + 24, x0 + 24 + i * 12, y0 + 30], fill=(80, 92, 110))
            d.rounded_rectangle([x0 + 12, y0 + 50, x1 - 12, y0 + 74], radius=6, fill=col)
            d.rounded_rectangle([x0 + 12, y0 + 84, x1 - 12, y0 + 116], radius=6, fill=(34, 42, 54))
            d.rounded_rectangle([x0 + 12, y0 + 126, x0 + 56, y0 + 152], radius=6, fill=col)
        d.rounded_rectangle([x0 + 12, y1 - 42, x1 - 12, y1 - 18], radius=6, fill=(26, 33, 43))


def m_write(d, t, acc):
    """свой вариант: строки печатаются"""
    x, y = 486, 156
    rr(d, [x, y, x + 190, y + 176], 12, fill=(20, 26, 34), outline=(52, 62, 78), w=2)
    widths = [150, 120, 160, 96]
    for i, w in enumerate(widths):
        p = min(1, max(0, (t - i * 0.15) / 0.3))
        if p > 0:
            d.rounded_rectangle([x + 18, y + 26 + i * 34, x + 18 + w * p, y + 38 + i * 34],
                                radius=5, fill=acc if i == 3 else (70, 82, 100))
    # курсор
    if t < 0.95 and int(t * 20) % 2 == 0:
        d.rectangle([x + 18, y + 128, x + 20, y + 142], fill=acc)


def m_contact(d, t, acc):
    """связаться: два пузыря и точка"""
    rr(d, [486, 140, 660, 208], 18, fill=(26, 33, 43), outline=(52, 62, 78), w=2)
    for i in range(3):
        on = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 6.28 - i * 1.1))
        d.ellipse([508 + i * 20, 166, 518 + i * 20, 176], fill=tuple(int(c * on) for c in acc))
    rr(d, [516, 226, 690, 294], 18, fill=acc)
    d.rounded_rectangle([538, 248, 660, 258], radius=5, fill=(12, 16, 20))
    d.rounded_rectangle([538, 266, 620, 274], radius=4, fill=(12, 16, 20))
    # стрелка
    x = 560 + 40 * min(1, t * 1.5)
    d.line([(556, 340), (x, 340)], fill=acc, width=7)
    d.polygon([(x, 329), (x + 18, 340), (x, 351)], fill=acc)


MOTIFS = {
    "cards": m_cards,
    "split": m_split,
    "write": m_write,
    "contact": m_contact,
}

SECTIONS = [
    ("scr_catalog.gif", "КАТАЛОГ", "5 услуг и свой вариант", "cards", (182, 255, 62)),
    ("scr_examples.gif", "ПРИМЕРЫ", "боты и сайты, по 4 штуки", "split", (76, 215, 240)),
    ("scr_custom.gif", "СВОЙ ВАРИАНТ", "опиши задачу — отвечу честно", "write", (222, 228, 238)),
    ("scr_contact.gif", "СВЯЗАТЬСЯ", "напишите — отвечу быстро", "contact", (61, 224, 160)),
]


def make(name, title, sub, motif, acc):
    base = bg()
    f_tag = font(21, 600)
    f_title = font(46, 800)
    f_sub = font(21, 400)

    frames = []
    steps = 12
    for i in range(steps + 1):
        t = i / steps
        fr = base.copy()
        d = ImageDraw.Draw(fr)

        d.text((54, 52), "РАЗДЕЛ", font=f_tag, fill=acc)
        d.rectangle([54, 84, 138, 87], fill=acc)

        d.text((52, 190), title, font=f_title, fill=WHITE)
        lines = sub.split(" ")
        # перенос подписи по строкам
        cur, out = "", []
        for w in lines:
            test = (cur + " " + w).strip()
            if d.textbbox((0, 0), test, font=f_sub)[2] < 340:
                cur = test
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        yy = 264
        for ln in out[:2]:
            d.text((54, yy), ln, font=f_sub, fill=MUTED)
            yy += 30

        MOTIFS[motif](d, t, acc)
        frames.append(fr)

    for _ in range(2):
        frames.append(frames[-1])

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    durations = [70] * (len(pal) - 1) + [2200]
    path = os.path.join(ASSETS, name)
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    pal[-1].save(os.path.join(OUT, name.replace(".gif", "-preview.png")))
    return name, os.path.getsize(path) // 1024


if __name__ == "__main__":
    for n, t, s, m, a in SECTIONS:
        print(*make(n, t, s, m, a))
