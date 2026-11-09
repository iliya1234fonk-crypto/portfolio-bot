# -*- coding: utf-8 -*-
"""Видео для всех разделов бота: 1280x720, 30 fps, без звука.

Сцены повторяют стиль фото (тёмный фон, Onest, акцентные чипы),
но с движением: мягкое появление, живые макеты ботов и сайтов,
световой дрейф и аккуратные переходы.
"""
import os
import math
import random
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "assets", "Onest.ttf")
OUT = os.path.join(HERE, "assets", "videos")
TMP = "/data/data/cat.narezany.margycode/cache/tmp/opencode/vframes"
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 720
FPS = 30
PI = math.pi

DARK_TOP = (11, 14, 19)
DARK_BOT = (20, 26, 34)
GRID = (25, 31, 40)
CARD = (20, 26, 34)
CARD2 = (17, 22, 29)
LINE = (38, 46, 58)
WHITE = (246, 248, 250)
MUTED = (138, 148, 166)
MUTED2 = (104, 116, 134)
MINT = (182, 255, 62)
CYAN = (76, 215, 240)
ORANGE = (255, 138, 61)
GREEN = (61, 224, 160)
BLUE = (106, 168, 255)
PAPER = (222, 228, 238)
BLACK = Image.new("RGBA", (W, H), (0, 0, 0, 255))

_fonts = {}


def fnt(size, weight=400):
    key = (size, weight)
    f = _fonts.get(key)
    if f is None:
        f = ImageFont.truetype(FONT, size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        _fonts[key] = f
    return f


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def eo(t):
    """ease-out cubic"""
    t = clamp(t)
    return 1 - (1 - t) ** 3


def eio(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def alpha(p, start, dur=0.28):
    return int(255 * eo((p - start) / dur)) if dur else 255


_BG = None


def bg():
    global _BG
    if _BG is None:
        strip = Image.new("RGB", (1, H))
        sd = ImageDraw.Draw(strip)
        for y in range(H):
            t = y / (H - 1)
            sd.point((0, y), fill=tuple(int(DARK_TOP[i] + (DARK_BOT[i] - DARK_TOP[i]) * t) for i in range(3)))
        img = strip.resize((W, H), Image.BILINEAR)
        d = ImageDraw.Draw(img)
        for x in range(0, W, 60):
            d.line([(x, 0), (x, H)], fill=GRID, width=1)
        for y in range(0, H, 60):
            d.line([(0, y), (W, y)], fill=GRID, width=1)
        _BG = img.convert("RGBA")
    return _BG.copy()


_glows = {}


def glow(color, size=760):
    key = (color, size)
    g = _glows.get(key)
    if g is None:
        g = Image.new("RGBA", (size, size), color + (0,))
        px = g.load()
        c = size / 2.0
        for y in range(size):
            for x in range(size):
                dist = math.hypot(x - c, y - c) / c
                a = int(46 * max(0.0, 1 - dist) ** 2.4)
                if a:
                    px[x, y] = color + (a,)
        _glows[key] = g
    return g


def put_glow(img, color, x, y, size=760):
    g = glow(color, size)
    img.paste(g, (int(x - size / 2), int(y - size / 2)), g)


def T(d, xy, s, size, weight=400, color=WHITE, a=255, anchor=None):
    if a <= 0:
        return
    d.text(xy, s, font=fnt(size, weight), fill=color + (int(a),), anchor=anchor)


def tw(d, s, size, weight=400):
    return d.textlength(s, font=fnt(size, weight))


def wrap(s, size, weight, maxw, maxlines=4):
    f = fnt(size, weight)
    out, cur = [], ""
    for w in s.split():
        test = (cur + " " + w).strip()
        if not cur or f.getlength(test) <= maxw:
            cur = test
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out[:maxlines]


def card(d, box, r=18, fill=CARD, line=LINE, a=255, width=2, acc=None, acc_w=4):
    if a <= 0:
        return
    d.rounded_rectangle(box, radius=r, fill=fill + (int(a),), outline=line + (int(a),), width=width)
    if acc:
        d.rounded_rectangle([box[0] + 1, box[1] + 16, box[0] + 1 + acc_w, box[3] - 16],
                            radius=acc_w // 2, fill=acc + (int(a),))


def pill(d, x, y, text, size, color, a=255, padx=18, pady=9, fill=None, outline=True, bold=700):
    f = fnt(size, bold)
    w = d.textlength(text, font=f) + padx * 2
    h = size + pady * 2
    if fill:
        d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill + (int(a),))
    if outline:
        d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, outline=color + (int(a),), width=2)
    T(d, (x + padx, y + pady - 1), text, size, bold, color, a)
    return w, h


def dot3(d, x, y, acc, p, r=5):
    for i in range(3):
        ph = (math.sin((p * 9) - i * 0.7) + 1) / 2
        a = int(70 + 150 * ph)
        cy = y - 4 * ph
        d.ellipse([x + i * 16, cy, x + i * 16 + r * 2, cy + r * 2], fill=acc + (a,))


def stars(d, x, y, size, acc, n=5, a=255, fill_frac=1.0):
    for i in range(n):
        cx = x + i * (size + 6) + size / 2
        cy = y + size / 2
        pts = []
        for k in range(10):
            ang = -PI / 2 + k * PI / 5
            rad = size / 2 if k % 2 == 0 else size / 4.6
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        if i < int(fill_frac * n + 0.0001):
            d.polygon(pts, fill=acc + (int(a),))
        else:
            d.line(pts + [pts[0]], fill=MUTED2 + (int(a),), width=2)


_particles = None


def particles(d, p, acc):
    global _particles
    if _particles is None:
        rnd = random.Random(7)
        _particles = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1.2, 3.0),
                       rnd.uniform(0.5, 1.4), rnd.randint(18, 54)) for _ in range(26)]
    for x0, y0, r, sp, al in _particles:
        y = (y0 - p * sp * 120) % H
        x = x0 + math.sin((p * 2 * PI) + y0) * 6
        d.ellipse([x, y, x + r * 2, y + r * 2], fill=acc + (al,))


def header(d, p, tag, title, sub, acc, x=72, title_size=86, maxw=600, sub_size=27):
    a = alpha(p, 0.02, 0.22)
    T(d, (x, 64), tag, 24, 600, acc, a)
    w = int(112 * eo((p - 0.04) / 0.25))
    if w > 4:
        d.rounded_rectangle([x, 102, x + w, 106], radius=2, fill=acc + (a,))
    lines = wrap(title, title_size, 800, maxw, 2)
    for i, ln in enumerate(lines):
        e = eo((p - 0.10 - i * 0.07) / 0.34)
        if e <= 0:
            continue
        T(d, (x - 4, 196 + i * (title_size + 8) + (1 - e) * 40), ln, title_size, 800, WHITE, int(255 * e))
    ty = 196 + len(lines) * (title_size + 8) + 18
    for i, ln in enumerate(wrap(sub, sub_size, 400, maxw - 40, 3)):
        e = eo((p - 0.26 - i * 0.05) / 0.30)
        if e > 0:
            T(d, (x, ty + i * (sub_size + 12)), ln, sub_size, 400, MUTED, int(255 * e))


def footer(d, p, acc, label="САЙТЫ И БОТЫ · @portfoli_robot"):
    a = alpha(p, 0.35, 0.3)
    if a <= 0:
        return
    d.line([(72, H - 56), (W - 72, H - 56)], fill=(255, 255, 255, 14), width=1)
    T(d, (72, H - 44), label, 18, 500, (122, 132, 148), a)
    for i in range(3):
        on = i == int((p * 3) % 3)
        d.ellipse([W - 72 - (3 - i) * 18, H - 42, W - 72 - (3 - i) * 18 + 8, H - 34],
                  fill=(acc if on else (58, 68, 82)) + (a,))


# ------------------------------------------------------------------ сцены ----
def scene_intro(d, p):
    acc = MINT
    a = alpha(p, 0.02, 0.22)
    T(d, (72, 66), "ПОРТФОЛИО", 24, 600, acc, a)
    w = int(150 * eo((p - 0.04) / 0.3))
    d.rounded_rectangle([72, 104, 72 + max(4, w), 108], radius=2, fill=acc + (a,))

    for i, (txt, col, size) in enumerate((("САЙТЫ", WHITE, 128), ("И БОТЫ", acc, 128))):
        e = eo((p - 0.08 - i * 0.12) / 0.4)
        if e <= 0:
            continue
        T(d, (68 - (1 - e) * 26, 176 + i * 132), txt, size, 800, col, int(255 * e))

    e = eo((p - 0.42) / 0.4)
    if e > 0:
        T(d, (74, 500), "под задачу · примеры внутри · цена и срок заранее", 27, 400, MUTED, int(255 * e))

    rx, ry = 906, 158
    items = (("Боты", MINT, "меню, заявки, запись"), ("Сайты", ORANGE, "визитка, лендинг"), ("Под задачу", CYAN, "своя идея"))
    for i, (t, col, sub) in enumerate(items):
        e = eo((p - 0.30 - i * 0.10) / 0.36)
        if e <= 0:
            continue
        y = ry + i * 150 + (1 - e) * 34
        a2 = int(255 * e)
        card(d, [rx, y, W - 72, y + 118], 20, CARD, LINE, a2)
        pulse = 1 + 0.10 * math.sin(p * 2 * PI * 1.2 + i)
        d.ellipse([rx + 24, y + 40, rx + 24 + 32 * pulse, y + 40 + 32 * pulse], fill=col + (a2,))
        T(d, (rx + 74, y + 32), t, 32, 700, WHITE, a2)
        T(d, (rx + 74, y + 76), sub, 19, 400, MUTED, a2)


def scene_catalog(d, p):
    acc = MINT
    header(d, p, "РАЗДЕЛ", "КАТАЛОГ", "5 услуг и свой вариант. Цена и срок — в сообщении.", acc)
    items = (
        ("Бот приёма заявок", "заявки в личку", CYAN),
        ("Бот записи", "услуга, мастер, время", CYAN),
        ("Сайт-визитка", "услуги и форма", ORANGE),
        ("Меню по QR", "кафе и доставка", GREEN),
        ("ИИ-бот", "ответы по прайсу", BLUE),
        ("Свой вариант", "опишите задачу", PAPER),
    )
    x0, y0 = 700, 118
    for i, (title, sub, col) in enumerate(items):
        e = eo((p - 0.10 - i * 0.085) / 0.34)
        if e <= 0:
            continue
        y = y0 + i * 84 + (1 - e) * 22
        a2 = int(255 * e)
        card(d, [x0, y, W - 72, y + 70], 16, CARD, LINE, a2, width=1)
        d.rounded_rectangle([x0 + 16, y + 18, x0 + 50, y + 52], radius=10, fill=col + (a2,))
        T(d, (x0 + 68, y + 14), title, 25, 700, WHITE, a2)
        T(d, (x0 + 68, y + 44), sub, 16, 400, MUTED, a2)
        T(d, (W - 108, y + 24), "›", 30, 700, col, a2)


def _panel(d, box, title, acc, a, sub="", p=0):
    card(d, box, 22, CARD2, LINE, a)
    x, y, x2, y2 = box
    d.ellipse([x + 22, y + 20, x + 34, y + 32], fill=acc + (a,))
    T(d, (x + 46, y + 13), title, 20, 700, WHITE, a)
    if sub:
        T(d, (x + 46, y + 40), sub, 15, 400, MUTED, a)
    d.line([(x, y + 70), (x2, y + 70)], fill=LINE + (a,), width=1)


def _bubble(d, box, a, fill=(30, 37, 48), accent=None, side="left"):
    d.rounded_rectangle(box, radius=16, fill=fill + (a,))
    if accent:
        d.line([(box[0] + 18, box[1] + box[3] - box[1] - 14),
                (box[0] + box[2] - box[0] - 18, box[1] + box[3] - box[1] - 14)],
               fill=accent + (int(a * 0.35),), width=3)


def _btn(d, box, label, acc, a, filled=False, size=15, press=False):
    if press:
        d.rounded_rectangle(box, radius=10, fill=acc + (a,))
        T(d, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, size, 700, (10, 14, 18), a, "mm")
    else:
        d.rounded_rectangle(box, radius=10, fill=(26, 33, 43, a), outline=(56, 66, 82, a), width=2)
        T(d, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, size, 600, acc if filled else WHITE, a, "mm")


def scene_zayavki(d, p):
    acc = CYAN
    header(d, p, "УСЛУГА · БОТ", "БОТ ПРИЁМА ЗАЯВОК", "Клиент пишет боту — заявка сразу падает в личку.", acc, title_size=68, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    _panel(d, box, "Бот приёма заявок", acc, a, "онлайн")
    x, y = 766, 218

    e = eo((p - 0.16) / 0.3)
    if e > 0:
        _bubble(d, [x, y, x + 300, y + 62], int(255 * e))
        T(d, (x + 16, y + 12), "Здравствуйте!", 18, 600, WHITE, int(255 * e))
        T(d, (x + 16, y + 36), "Нужен бот для заявок", 16, 400, MUTED, int(255 * e))
    y += 76
    e2 = eo((p - 0.28) / 0.25)
    if e2 > 0:
        _bubble(d, [x, y, x + 196, y + 34], int(255 * e2))
        dot3(d, x + 18, y + 13, acc, p, 4)

    by = y + 52
    labels = ("Каталог", "Оставить заявку", "Связаться")
    for i, lab in enumerate(labels):
        e3 = eo((p - 0.34 - i * 0.07) / 0.26)
        if e3 <= 0:
            continue
        press = i == 1 and p > 0.58
        _btn(d, [x, by + i * 44 + (1 - e3) * 8, x + 320, by + i * 44 + 34 + (1 - e3) * 8],
             lab, acc, int(255 * e3), filled=(i == 1), press=press)

    if p > 0.66:
        e4 = eo((p - 0.66) / 0.3)
        yy = by + 3 * 44 + 8
        d.rounded_rectangle([x, yy, x + 320, yy + 48], radius=14, fill=(22, 30, 26, int(255 * e4)))
        T(d, (x + 16, yy + 8), "Заявка #12 создана", 17, 700, acc, int(255 * e4))
        T(d, (x + 16, yy + 28), "уведомление ушло в личку", 13, 400, MUTED, int(255 * e4))

    e5 = eo((p - 0.78) / 0.3)
    if e5 > 0:
        yy = 470 + (1 - e5) * 30
        card(d, [x, yy, x + 320, yy + 118], 16, (24, 31, 40), (56, 66, 82), int(255 * e5))
        T(d, (x + 16, yy + 12), "ЗАЯВКА #12", 13, 700, acc, int(255 * e5))
        T(d, (x + 16, yy + 36), "Иван · @ivan", 18, 600, WHITE, int(255 * e5))
        T(d, (x + 16, yy + 62), "бот для заявок · 750 ₽", 14, 400, MUTED, int(255 * e5))
        _btn(d, [x + 16, yy + 86, x + 130, yy + 110], "Ответить", acc, int(255 * e5), filled=True, size=12)
        d.ellipse([x + 288, yy + 94, x + 300, yy + 106], fill=acc + (int(255 * e5),))


def scene_zapis(d, p):
    acc = CYAN
    header(d, p, "УСЛУГА · БОТ", "БОТ ЗАПИСИ", "Услуга, мастер, время. Напоминание за час.", acc, title_size=76, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    _panel(d, box, "Запись онлайн", acc, a, "салон · 3 шага")
    x, y = 766, 206

    steps = ("Услуга", "Мастер", "Время")
    for i, s in enumerate(steps):
        done = p > 0.20 + i * 0.20
        e = eo((p - 0.10 - i * 0.05) / 0.25)
        if e <= 0:
            continue
        col = acc if done else MUTED2
        d.ellipse([x + i * 132, y, x + i * 132 + 30, y + 30],
                  fill=(acc + (int(255 * e),)) if done else (30, 37, 48, int(255 * e)))
        T(d, (x + i * 132 + 15, y + 15), str(i + 1), 15, 800,
          (10, 14, 18) if done else MUTED, int(255 * e), "mm")
        T(d, (x + i * 132 + 38, y + 6), s, 15, 600, col, int(255 * e))
        if i < 2:
            d.line([(x + i * 132 + 30, y + 15), (x + i * 132 + 116, y + 15)],
                   fill=(acc if done else LINE) + (int(255 * e),), width=2)

    y += 58
    e = eo((p - 0.18) / 0.28)
    if e > 0:
        for i, (lab, col) in enumerate((("Маникюр", acc), ("Педикюр", None))):
            bw = 138
            bx = x + i * (bw + 12) + (1 - e) * 10
            d.rounded_rectangle([bx, y, bx + bw, y + 46], radius=12,
                                fill=(26, 33, 43, int(255 * e)) if not col else (int(col[0] * .16), int(col[1] * .22), int(col[2] * .18), int(255 * e)),
                                outline=(col or (56, 66, 82)) + (int(255 * e),), width=2)
            T(d, (bx + 18, y + 13), lab, 17, 700, WHITE if col else MUTED, int(255 * e))
    y += 72
    e = eo((p - 0.36) / 0.28)
    if e > 0:
        for i, name in enumerate(("Анна", "Ирина")):
            bw = 150
            bx = x + i * (bw + 12) + (1 - e) * 10
            sel = i == 0
            d.rounded_rectangle([bx, y, bx + bw, y + 62], radius=14, fill=(26, 33, 43, int(255 * e)),
                                outline=(acc if sel else (56, 66, 82)) + (int(255 * e),), width=2)
            d.ellipse([bx + 14, y + 12, bx + 52, y + 50], fill=((acc if sel else LINE) + (int(255 * e),)))
            T(d, (bx + 64, y + 12), name, 18, 700, WHITE, int(255 * e))
            T(d, (bx + 64, y + 36), "свободна", 13, 400, MUTED, int(255 * e))
    y += 88
    e = eo((p - 0.50) / 0.28)
    if e > 0:
        slots = ("10:00", "12:30", "15:00", "18:00")
        for i, s in enumerate(slots):
            bx = x + (i % 2) * 168
            by = y + (i // 2) * 58
            sel = i == 2 and p > 0.64
            pulse = int(255 * e)
            if sel:
                ring = 6 + 3 * math.sin(p * 2 * PI * 2)
                d.rounded_rectangle([bx - ring / 2, by - ring / 2, bx + 160 + ring / 2, by + 44 + ring / 2],
                                    radius=16, outline=acc + (int(120 * e),), width=2)
            d.rounded_rectangle([bx, by, bx + 160, by + 44], radius=12,
                                fill=((int(acc[0] * .9), int(acc[1] * .9), int(acc[2] * .9), pulse) if sel else (26, 33, 43, pulse)),
                                outline=(acc if sel else (56, 66, 82)) + (pulse,), width=2)
            T(d, (bx + 20, by + 11), s, 18, 700, (10, 14, 18) if sel else WHITE, pulse)

    e = eo((p - 0.80) / 0.3)
    if e > 0:
        yy = 548 + (1 - e) * 20
        d.rounded_rectangle([x, yy, x + 320, yy + 46], radius=14, fill=(22, 30, 26, int(255 * e)))
        T(d, (x + 16, yy + 9), "Записано: 15:00 · Анна", 16, 700, acc, int(255 * e))
        T(d, (x + 16, yy + 28), "напомню за час", 12, 400, MUTED, int(255 * e))


def scene_site(d, p):
    acc = ORANGE
    header(d, p, "УСЛУГА · САЙТ", "САЙТ-ВИЗИТКА", "Услуги, цены, фото. Заявки приходят в телеграм.", acc, title_size=72, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    # browser
    card(d, box, 20, CARD2, LINE, a)
    x, y, x2, y2 = box
    d.line([(x, y + 46), (x2, y + 46)], fill=LINE + (a,), width=1)
    for i in range(3):
        d.ellipse([x + 18 + i * 16, y + 16, x + 28 + i * 16, y + 26], fill=(70, 80, 96, a))
    d.rounded_rectangle([x + 76, y + 12, x2 - 18, y + 32], radius=8, fill=(26, 33, 43, a))
    T(d, (x + 90, y + 15), "master.ru", 13, 500, MUTED, a)

    # scrollable content
    scroll = 0
    if p > 0.52:
        scroll = int(eio((p - 0.52) / 0.4) * 150)

    cy = y + 62 - scroll
    e = eo((p - 0.18) / 0.3)
    if e > 0:
        T(d, (x + 24, cy + 10), "МАНИКЮР", 44, 800, WHITE, int(255 * e))
        T(d, (x + 24, cy + 58), "аккуратно, с идеей", 15, 400, MUTED, int(255 * e))
        bb = [x + 24, cy + 86, x + 152, cy + 124]
        _btn(d, bb, "Записаться", acc, int(255 * e), press=(0.30 < p < 0.40), size=15)
        d.rounded_rectangle([x + 216, cy + 10, x2 - 24, cy + 130], radius=14, fill=(28, 36, 46, int(255 * e)),
                            outline=(56, 66, 82, int(255 * e)), width=1)
        d.ellipse([x + 252, cy + 40, x + 322, cy + 110], outline=acc + (int(255 * e),), width=3)
        d.ellipse([x + 275, cy + 63, x + 299, cy + 87], fill=acc + (int(255 * e),))

    cy += 158
    e = eo((p - 0.36) / 0.3)
    if e > 0:
        for i, (t, price) in enumerate((("Маникюр", "1 500 ₽"), ("Педикюр", "1 900 ₽"), ("Дизайн", "500 ₽"))):
            yy = cy + i * 52
            d.rounded_rectangle([x + 24, yy, x2 - 24, yy + 42], radius=10, fill=(24, 31, 40, int(255 * e)))
            T(d, (x + 38, yy + 10), t, 15, 600, WHITE, int(255 * e))
            T(d, (x2 - 90, yy + 10), price, 15, 700, acc, int(255 * e))

    e = eo((p - 0.70) / 0.3)
    if e > 0:
        yy = cy + 178
        d.rounded_rectangle([x + 24, yy, x2 - 24, yy + 58], radius=12, fill=(26, 33, 43, int(255 * e)),
                            outline=LINE + (int(255 * e),), width=1)
        T(d, (x + 38, yy + 10), "Имя и телефон", 14, 400, MUTED, int(255 * e))
        _btn(d, [x + 190, yy + 10, x2 - 36, yy + 48], "Отправить", acc, int(255 * e), press=p > 0.86, size=14)
        T(d, (x + 24, yy + 70), "+ заявка в телеграм", 13, 600, GREEN, int(255 * e))


def scene_menu(d, p):
    acc = GREEN
    header(d, p, "УСЛУГА · МЕНЮ", "МЕНЮ ПО QR", "Гость сканирует QR — видит меню и заказывает без звонка.", acc, title_size=76, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    _panel(d, box, "Меню кафе", acc, a, "QR · заказ без звонка")

    # QR
    qx, qy, qs = 766, 206, 118
    d.rounded_rectangle([qx - 10, qy - 10, qx + qs + 10, qy + qs + 10], radius=12, fill=(238, 242, 247, a))
    modules = [(2, 2), (2, 3), (2, 4), (3, 2), (4, 2), (9, 2), (10, 2), (11, 2), (11, 3), (11, 4),
               (2, 9), (2, 10), (3, 11), (4, 11), (7, 6), (8, 6), (6, 8), (9, 8), (7, 9), (10, 10),
               (5, 7), (8, 3), (6, 1), (1, 6), (12, 6), (12, 10), (7, 12), (4, 6), (9, 5)]
    cell = qs / 14
    for mx, my in modules:
        d.rectangle([qx + mx * cell, qy + my * cell, qx + (mx + 1) * cell + 1, qy + (my + 1) * cell + 1],
                    fill=(18, 24, 31, a))
    for (fx, fy) in ((0, 0), (11, 0), (0, 11)):
        d.rectangle([qx + fx * cell, qy + fy * cell, qx + (fx + 3) * cell, qy + (fy + 3) * cell],
                    outline=(18, 24, 31, a), width=int(cell))
    scan = qy + (qs + 10) * clamp((p - 0.08) / 0.34)
    if 0.06 < p < 0.46:
        d.rectangle([qx - 8, scan, qx + qs + 8, scan + 3], fill=acc + (int(160 * a / 255),))

    T(d, (qx + qs + 30, qy + 6), "Наведите камеру", 15, 600, WHITE, a)
    T(d, (qx + qs + 30, qy + 30), "и меню откроется", 14, 400, MUTED, a)
    d.rounded_rectangle([qx + qs + 30, qy + 62, qx + qs + 30 + 286, qy + 96], radius=10,
                        fill=(26, 33, 43, a), outline=(56, 66, 82, a), width=1)
    T(d, (qx + qs + 44, qy + 72), "меню · цены · заказ", 13, 500, MUTED, a)

    y = 348
    items = (("Капучино", "190 ₽"), ("Круассан", "150 ₽"), ("Паста", "390 ₽"))
    for i, (t, price) in enumerate(items):
        e = eo((p - 0.26 - i * 0.09) / 0.3)
        if e <= 0:
            continue
        yy = y + i * 58 + (1 - e) * 14
        aa = int(255 * e)
        d.rounded_rectangle([766, yy, 1174, yy + 46], radius=12, fill=(24, 31, 40, aa))
        d.rounded_rectangle([780, yy + 9, 808, yy + 37], radius=7, fill=acc + (aa,))
        T(d, (822, yy + 11), t, 17, 600, WHITE, aa)
        T(d, (1100, yy + 11), price, 17, 700, WHITE, aa)

    e = eo((p - 0.64) / 0.3)
    if e > 0:
        _btn(d, [766, 540, 1174, 586], "Заказать", acc, int(255 * e), press=p > 0.82, size=17)
    e = eo((p - 0.84) / 0.3)
    if e > 0:
        T(d, (766, 596), "Заказ принят · гость доволен", 13, 600, acc, int(255 * e))


def scene_ai(d, p):
    acc = BLUE
    header(d, p, "УСЛУГА · ИИ", "ИИ-БОТ", "Отвечает клиентам по вашему прайсу и документам. 24/7.", acc, title_size=78, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    _panel(d, box, "ИИ-бот", acc, a, "отвечает сам")
    T(d, (1068, 138), "24/7", 18, 800, acc, a)

    x = 766
    msgs = (
        (0.14, "left", "Сколько стоит сайт?"),
        (0.38, "right", "Визитка — 500 ₽, 2–4 дня"),
        (0.60, "left", "А если срочно?"),
        (0.80, "right", "+30% к цене, 1–2 дня"),
    )
    y = 208
    for i, (start, side, txt) in enumerate(msgs):
        e = eo((p - start) / 0.24)
        if e <= 0:
            continue
        aa = int(255 * e)
        f = fnt(16, 500)
        w = min(300, d.textlength(txt, font=f) + 34)
        if side == "left":
            bx = [x, y, x + w, y + 48]
            fill = (30, 37, 48)
            tx = x + 17
        else:
            bx = [x + 320 - w, y, x + 320, y + 48]
            fill = (int(acc[0] * .22), int(acc[1] * .3), int(acc[2] * .34))
            tx = bx[0] + 17
        d.rounded_rectangle(bx, radius=14, fill=fill + (aa,))
        T(d, (tx, y + 14), txt, 16, 500, WHITE, aa)
        y += 62

    # typing indicator between messages
    for start, yy in ((0.28, 208 + 62), (0.70, 208 + 62 + 62 + 62)):
        if start < p < start + 0.10:
            aa = int(255 * eo((p - start) / 0.05))
            d.rounded_rectangle([x, yy, x + 86, yy + 34], radius=14, fill=(30, 37, 48, aa))
            dot3(d, x + 18, yy + 13, acc, p, 4)

    e = eo((p - 0.90) / 0.06)
    if e > 0:
        d.rounded_rectangle([x, 500, x + 320, 560], radius=14, fill=(22, 30, 26, int(255 * e)))
        T(d, (x + 16, 508), "Отвечает без вас", 15, 700, acc, int(255 * e))
        T(d, (x + 16, 530), "клиент получил ответ за 2 сек", 12, 400, MUTED, int(255 * e))


def scene_custom(d, p):
    acc = PAPER
    header(d, p, "УСЛУГА · СВОЙ", "СВОЙ ВАРИАНТ", "Опишите задачу — скажу, возьмусь или нет, и сколько стоит.", PAPER, title_size=72, maxw=560)
    a = alpha(p, 0.10, 0.3)
    box = [740, 118, 1208, 620]
    _panel(d, box, "Новая задача", PAPER, a, "свободная форма")

    e = eo((p - 0.18) / 0.3)
    if e > 0:
        aa = int(255 * e)
        d.rounded_rectangle([766, 206, 1174, 430], radius=16, fill=(24, 31, 40, aa),
                            outline=(56, 66, 82, aa), width=1)
        text = "Нужен бот для записи в салон: услуги, мастера, время, напоминания. И чтобы заявки падали в телеграм."
        lines = wrap(text, 19, 400, 372, 7)
        shown = int(len(text) * clamp((p - 0.24) / 0.42))
        left = shown
        caret_line = 0
        yy = 224
        for i, ln in enumerate(lines):
            part = ln[:max(0, left)]
            left -= len(ln) + 1
            T(d, (786, yy + i * 27), part, 19, 400, WHITE, aa)
            if left <= 0 and shown < len(text):
                caret_line = i
        if (p * 4) % 1 < 0.5:
            T(d, (786 + 0, 224 + caret_line * 27 + 2), "|", 19, 400, acc, aa)

    e = eo((p - 0.66) / 0.25)
    if e > 0:
        aa = int(255 * e)
        pill(d, 766, 452, "срок и цену скажу точно", 15, acc, aa, fill=(28, 36, 46))
        pill(d, 1042, 452, "без предоплаты", 15, GREEN, aa)

    e = eo((p - 0.80) / 0.3)
    if e > 0:
        _btn(d, [766, 540, 994, 586], "Отправить", acc, int(255 * e), press=p > 0.92, size=17)
        T(d, (1012, 552), "ответ в течение дня", 13, 400, MUTED, int(255 * e))


def scene_examples(d, p):
    acc = CYAN
    header(d, p, "РАЗДЕЛ", "ПРИМЕРЫ", "8 сценариев: боты и сайты. Можно открыть и посмотреть.", acc, title_size=84, maxw=520)
    cols = (
        (700, "БОТЫ", MINT, ("Запись", "Заявки", "Меню", "ИИ")),
        (960, "САЙТЫ", ORANGE, ("Визитка", "Лендинг", "Портфолио", "Каталог")),
    )
    for cx, title, col, items in cols:
        e = eo((p - 0.12) / 0.3)
        if e <= 0:
            continue
        aa = int(255 * e)
        card(d, [cx, 132, cx + 240, 600], 20, CARD, LINE, aa)
        T(d, (cx + 18, 150), title, 17, 700, col, aa)
        for i, lab in enumerate(items):
            e2 = eo((p - 0.22 - i * 0.07) / 0.3)
            if e2 <= 0:
                continue
            yy = 196 + i * 84 + (1 - e2) * 12
            aa2 = int(255 * e2)
            d.rounded_rectangle([cx + 16, yy, cx + 224, yy + 66], radius=12, fill=(26, 33, 43, aa2))
            d.rounded_rectangle([cx + 28, yy + 16, cx + 62, yy + 50], radius=9, fill=col + (aa2,))
            T(d, (cx + 74, yy + 14), lab, 17, 600, WHITE, aa2)
            d.rounded_rectangle([cx + 74, yy + 40, cx + 74 + 78, yy + 46], radius=3, fill=(70, 82, 100, aa2))
        e3 = eo((p - 0.62) / 0.3)
        if e3 > 0:
            d.rounded_rectangle([cx + 16, 560, cx + 224, 586], radius=13, fill=(24, 31, 40, int(255 * e3)))
            T(d, (cx + 28, 565), "открыть в боте", 12, 500, MUTED, int(255 * e3))
            T(d, (cx + 186, 564), "→", 16, 700, col, int(255 * e3))


def scene_reviews(d, p):
    acc = MINT
    header(d, p, "РАЗДЕЛ", "ОТЗЫВЫ", "Что пишут после работы. Живые, без выдумки.", acc, title_size=84, maxw=520)
    quotes = (
        ("Иван", "Сделал бота за 2 дня, всё работает. Заявки приходят в личку.", CYAN),
        ("Мария", "Сайт открывается с телефона, заявки в телеграме. Довольна.", ORANGE),
        ("Артём", "Понятно объяснил, показал демо до оплаты.", GREEN),
    )
    for i, (name, text, col) in enumerate(quotes):
        e = eo((p - 0.12 - i * 0.12) / 0.32)
        if e <= 0:
            continue
        yy = 140 + i * 158 + (1 - e) * 26
        aa = int(255 * e)
        card(d, [700, yy, 1208, yy + 136], 18, CARD, LINE, aa)
        d.ellipse([716, yy + 20, 756, yy + 60], fill=col + (aa,))
        T(d, (736, yy + 40), name[0], 20, 800, (10, 14, 18), aa, "mm")
        T(d, (768, yy + 16), name, 18, 700, WHITE, aa)
        stars(d, 768, yy + 46, 13, acc, 5, aa)
        for j, ln in enumerate(wrap(text, 16, 400, 400, 2)):
            T(d, (716, yy + 74 + j * 24), ln, 16, 400, MUTED, aa)

    e = eo((p - 0.72) / 0.3)
    if e > 0:
        aa = int(255 * e)
        d.rounded_rectangle([700, 620 - 26, 860, 620], radius=16, fill=(22, 30, 26, aa))
        T(d, (716, 602), "средняя оценка 5.0", 14, 700, acc, aa)


def scene_contact(d, p):
    acc = GREEN
    header(d, p, "РАЗДЕЛ", "СВЯЗАТЬСЯ", "Напишите — отвечу быстро. Сообщение в один клик.", acc, title_size=84, maxw=520)
    a = alpha(p, 0.12, 0.3)
    box = [700, 130, 1208, 600]
    _panel(d, box, "Чат с продавцом", acc, a, "обычно отвечаю днём")

    e = eo((p - 0.20) / 0.3)
    if e > 0:
        aa = int(255 * e)
        d.rounded_rectangle([724, 224, 1184, 296], radius=16, fill=(30, 37, 48, aa))
        T(d, (744, 238), "Здравствуйте! Нужен сайт для мастера.", 17, 500, WHITE, aa)
        T(d, (744, 264), "Сколько будет стоить?", 17, 500, WHITE, aa)

    e = eo((p - 0.40) / 0.3)
    if e > 0:
        aa = int(255 * e)
        d.rounded_rectangle([864, 312, 1184, 360], radius=16, fill=(int(acc[0] * .22), int(acc[1] * .32), int(acc[2] * .3), aa))
        T(d, (884, 324), "Визитка 500 ₽, 2–4 дня", 16, 600, WHITE, aa)

    e = eo((p - 0.56) / 0.3)
    if e > 0:
        aa = int(255 * e)
        d.rounded_rectangle([724, 380, 830, 420], radius=20, fill=(30, 37, 48, aa))
        dot3(d, 746, 394, acc, p, 5)

    e = eo((p - 0.70) / 0.3)
    if e > 0:
        aa = int(255 * e)
        pulse = 0.5 + 0.5 * math.sin(p * 2 * PI * 1.5)
        d.rounded_rectangle([724, 468, 1184, 540], radius=18,
                            fill=(int(acc[0] * (0.82 + 0.1 * pulse)), int(acc[1] * (0.82 + 0.1 * pulse)), int(acc[2] * (0.82 + 0.1 * pulse)), aa))
        T(d, (954, 504), "Написать в боте", 23, 800, (10, 14, 18) if e > 0.6 else WHITE, aa, "mm")
        T(d, (724, 556), "без анкет и ожидания", 14, 400, MUTED, aa)


def scene_about(d, p):
    acc = CYAN
    header(d, p, "РАЗДЕЛ", "О БОТЕ", "Коротко: что делаю и как проходит работа.", acc, title_size=84, maxw=520)
    rows = (
        ("Что делаю", "сайты и телеграм-боты под задачу", MINT),
        ("Для кого", "бизнес, учёба, личные проекты", CYAN),
        ("Как работаем", "обсуждаем → демо → оплата → доступ", ORANGE),
        ("Правки", "мелкие по задаче — сразу", GREEN),
    )
    for i, (t, sub, col) in enumerate(rows):
        e = eo((p - 0.14 - i * 0.10) / 0.32)
        if e <= 0:
            continue
        yy = 138 + i * 112 + (1 - e) * 20
        aa = int(255 * e)
        card(d, [700, yy, 1208, yy + 92], 16, CARD, LINE, aa, acc=col)
        T(d, (720, yy + 16), t, 18, 700, WHITE, aa)
        T(d, (720, yy + 46), sub, 16, 400, MUTED, aa)
    e = eo((p - 0.62) / 0.3)
    if e > 0:
        aa = int(255 * e)
        pill(d, 700, 588, "цена и срок заранее", 15, acc, aa, fill=(28, 36, 46))
        pill(d, 936, 588, "демо до оплаты", 15, MINT, aa)


def _mini_chat(d, box, name, acc, a, p, lines, buttons):
    card(d, box, 16, CARD2, LINE, a)
    x, y, x2, y2 = box
    d.ellipse([x + 14, y + 14, x + 26, y + 26], fill=acc + (a,))
    T(d, (x + 34, y + 8), name, 16, 700, WHITE, a)
    d.line([(x, y + 38), (x2, y + 38)], fill=LINE + (a,), width=1)
    yy = y + 50
    for i, (txt, side) in enumerate(lines):
        e = eo((p - 0.20 - i * 0.08) / 0.26)
        if e <= 0:
            continue
        aa = int(255 * e)
        f = fnt(12, 500)
        bw = min(x2 - x - 24, d.textlength(txt, font=f) + 22)
        bx = x + 12 if side == "l" else x2 - 12 - bw
        fill = (30, 37, 48) if side == "l" else (int(acc[0] * .20), int(acc[1] * .28), int(acc[2] * .30))
        d.rounded_rectangle([bx, yy, bx + bw, yy + 28], radius=10, fill=fill + (aa,))
        T(d, (bx + 11, yy + 7), txt, 12, 500, WHITE, aa)
        yy += 36
    for i, lab in enumerate(buttons[:2]):
        e = eo((p - 0.52 - i * 0.06) / 0.26)
        if e <= 0:
            continue
        aa = int(255 * e)
        by = y2 - 54 + i * 24
        d.rounded_rectangle([x + 12, by, x2 - 12, by + 19], radius=8,
                            fill=(26, 33, 43, aa),
                            outline=(acc if i == 0 else (56, 66, 82)) + (aa,), width=1)
        T(d, ((x + x2) / 2, by + 9), lab, 10, 600, acc if i == 0 else MUTED, aa, "mm")


def scene_ex_bots(d, p):
    acc = CYAN
    header(d, p, "ПРИМЕРЫ · БОТЫ", "4 СЦЕНАРИЯ", "Запись, заявки, меню, ответы.", acc, title_size=90, maxw=520)
    boxes = (
        (686, 128, 936, 372, "Бот записи", (("Здравствуйте!", "l"), ("Хочу записаться", "l"), ("15:00 · Анна", "r")), ("Выбрать время", "Напоминание")),
        (952, 128, 1202, 372, "Бот заявок", (("Нужен бот", "l"), ("Для магазина", "l"), ("Заявка #12", "r")), ("Оставить заявку", "Ответить")),
        (686, 388, 936, 632, "Меню по QR", (("Сканирую QR", "l"), ("Капучино 190 ₽", "r"), ("Заказ принят", "r")), ("Открыть меню", "Заказать")),
        (952, 388, 1202, 632, "ИИ-бот", (("Сколько стоит?", "l"), ("Визитка 500 ₽", "r"), ("Спасибо!", "l")), ("Спросить ещё", "Прайс")),
    )
    active = int((p * 4.2) % 4)
    for i, (x, y, x2, y2, name, lines, buttons) in enumerate(boxes):
        e = eo((p - 0.10 - i * 0.10) / 0.34)
        if e <= 0:
            continue
        a = int(255 * e)
        yy = y + (1 - e) * 26
        b = [x, yy, x2, yy + (y2 - y)]
        _mini_chat(d, b, name, acc, a, p, lines, buttons)
        if i == active:
            pulse = (math.sin(p * 2 * PI * 1.5) + 1) / 2
            d.rounded_rectangle([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3], radius=19,
                                outline=acc + (int(70 + 90 * pulse),), width=2)
    pills = (("свои кнопки", MINT), ("свои тексты", CYAN), ("заявки в личку", ORANGE), ("срок 1–3 дня", GREEN))
    for i, (t, col) in enumerate(pills):
        e = eo((p - 0.42 - i * 0.09) / 0.3)
        if e <= 0:
            continue
        pill(d, 72 + (i % 2) * 196, 508 + (i // 2) * 44, t, 16, col, int(255 * e), fill=(26, 33, 43))


def _mini_site(d, box, name, kind, acc, a, p):
    card(d, box, 16, CARD2, LINE, a)
    x, y, x2, y2 = box
    d.line([(x, y + 34), (x2, y + 34)], fill=LINE + (a,), width=1)
    for i in range(3):
        d.ellipse([x + 12 + i * 12, y + 12, x + 19 + i * 12, y + 19], fill=(70, 80, 96, a))
    d.rounded_rectangle([x + 52, y + 9, x2 - 12, y + 23], radius=6, fill=(26, 33, 43, a))
    T(d, (x + 60, y + 10), name.lower() + ".ru", 10, 500, MUTED, a)
    cx, cy = x + 14, y + 44
    cw = x2 - x - 28
    if kind in ("визитка", "портфолио"):
        ts = 24
        while ts > 14 and d.textlength(name.upper(), font=fnt(ts, 800)) > cw - 96:
            ts -= 1
        T(d, (cx, cy), name.upper(), ts, 800, WHITE, a)
        d.rounded_rectangle([cx, cy + 34, cx + cw * 0.55, cy + 42], radius=3, fill=(70, 82, 100, a))
        d.rounded_rectangle([cx, cy + 50, cx + cw * 0.38, cy + 58], radius=3, fill=(70, 82, 100, a))
        d.rounded_rectangle([cx, cy + 72, cx + 92, cy + 102], radius=10, fill=acc + (a,))
        T(d, (cx + 46, cy + 87), "Записаться", 10, 700, (10, 14, 18), a, "mm")
        d.rounded_rectangle([cx + cw - 86, cy, cx + cw, cy + 106], radius=12, fill=(28, 36, 46, a),
                            outline=(56, 66, 82, a), width=1)
        d.ellipse([cx + cw - 64, cy + 30, cx + cw - 22, cy + 72], outline=acc + (a,), width=2)
        if kind == "портфолио":
            for i in range(2):
                for j in range(2):
                    bx = cx + i * 68
                    by = cy + 112 + j * 44
                    d.rounded_rectangle([bx, by, bx + 58, by + 34], radius=8, fill=(30, 38, 48, a))
    else:
        T(d, (cx, cy), name.upper(), 20, 800, WHITE, a)
        d.rounded_rectangle([cx, cy + 30, cx + cw, cy + 92], radius=10, fill=(28, 36, 46, a),
                            outline=acc + (int(a * .6),), width=1)
        d.rounded_rectangle([cx + 14, cy + 46, cx + cw * 0.6, cy + 56], radius=4, fill=(70, 82, 100, a))
        d.rounded_rectangle([cx + 14, cy + 66, cx + 92, cy + 82], radius=8, fill=acc + (a,))
        for i in range(3 if kind == "каталог" else 2):
            by = cy + 106 + i * 34
            d.rounded_rectangle([cx, by, cx + cw, by + 26], radius=8, fill=(24, 31, 40, a))
            d.rounded_rectangle([cx + 8, by + 6, cx + 22, by + 20], radius=5, fill=acc + (int(a * .7),))
            d.rounded_rectangle([cx + 30, by + 8, cx + cw * 0.5, by + 12], radius=2, fill=(70, 82, 100, a))
            d.rounded_rectangle([cx + cw - 46, by + 8, cx + cw - 8, by + 18], radius=3, fill=(70, 82, 100, a))


def scene_ex_sites(d, p):
    acc = ORANGE
    header(d, p, "ПРИМЕРЫ · САЙТЫ", "4 СЦЕНАРИЯ", "Визитка, лендинг, портфолио, каталог.", acc, title_size=88, maxw=570)
    boxes = (
        (686, 128, 936, 372, "Визитка", "визитка"),
        (952, 128, 1202, 372, "Лендинг", "лендинг"),
        (686, 388, 936, 632, "Портфолио", "портфолио"),
        (952, 388, 1202, 632, "Каталог", "каталог"),
    )
    for i, (x, y, x2, y2, name, kind) in enumerate(boxes):
        e = eo((p - 0.10 - i * 0.10) / 0.34)
        if e <= 0:
            continue
        a = int(255 * e)
        yy = y + (1 - e) * 26
        _mini_site(d, [x, yy, x2, yy + (y2 - y)], name, kind, acc, a, p)
    pills = (("под телефон", CYAN), ("заявка в телеграм", GREEN), ("без лишнего", MINT), ("срок 2–4 дня", ORANGE))
    for i, (t, col) in enumerate(pills):
        e = eo((p - 0.42 - i * 0.09) / 0.3)
        if e <= 0:
            continue
        pill(d, 72 + (i % 2) * 196, 508 + (i // 2) * 44, t, 16, col, int(255 * e), fill=(26, 33, 43))


def scene_trust(d, p):
    acc = GREEN
    header(d, p, "КАК Я РАБОТАЮ", "4 ШАГА", "Понятные условия, без сюрпризов по ходу.", acc, title_size=92, maxw=540)
    steps = (
        ("1. Обсуждаем задачу", "Пишете, что нужно — называю цену и срок заранее.", CYAN),
        ("2. Показываю демо", "Сначала видите результат, потом решаете по оплате.", MINT),
        ("3. Передаю всё", "Доступ и исходники у вас, проект остаётся вашим.", ORANGE),
        ("4. Остаюсь на связи", "Мелкие правки по задаче делаю сразу.", GREEN),
    )
    for i, (title, sub, col) in enumerate(steps):
        e = eo((p - 0.10 - i * 0.11) / 0.34)
        if e <= 0:
            continue
        yy = 140 + i * 122 + (1 - e) * 24
        a = int(255 * e)
        card(d, [700, yy, 1208, yy + 102], 16, CARD, LINE, a, acc=col)
        d.ellipse([720, yy + 20, 764, yy + 64], fill=col + (a,))
        T(d, (742, yy + 42), str(i + 1), 20, 800, (10, 14, 18), a, "mm")
        T(d, (782, yy + 18), title, 19, 700, WHITE, a)
        T(d, (782, yy + 48), sub, 15, 400, MUTED, a)
        if i == int(p * 5) and p < 0.92:
            pulse = (math.sin(p * 2 * PI * 1.8) + 1) / 2
            d.rounded_rectangle([697, yy - 3, 1211, yy + 105], radius=19,
                                outline=col + (int(50 + 80 * pulse),), width=2)
    e = eo((p - 0.74) / 0.3)
    if e > 0:
        pill(d, 72, 600, "цена и срок заранее", 15, acc, int(255 * e), fill=(28, 36, 46))
        pill(d, 320, 600, "демо до оплаты", 15, MINT, int(255 * e), fill=(28, 36, 46))


# ------------------------------------------------------------------ рендер ----
SCENES = {
    "intro": (6.0, MINT, scene_intro),
    "catalog": (8.0, MINT, scene_catalog),
    "svc_zayavki": (8.0, CYAN, scene_zayavki),
    "svc_zapis": (8.5, CYAN, scene_zapis),
    "svc_site": (8.5, ORANGE, scene_site),
    "svc_menu": (8.0, GREEN, scene_menu),
    "svc_ai": (8.0, BLUE, scene_ai),
    "svc_custom": (7.0, PAPER, scene_custom),
    "examples": (7.5, CYAN, scene_examples),
    "reviews": (7.5, MINT, scene_reviews),
    "contact": (7.0, GREEN, scene_contact),
    "about": (7.5, CYAN, scene_about),
    "ex_bots": (8.5, CYAN, scene_ex_bots),
    "ex_sites": (8.5, ORANGE, scene_ex_sites),
    "trust": (9.0, GREEN, scene_trust),
}


def render(name, seconds, acc, scene, fps=FPS):
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    frames = int(seconds * fps)
    for fi in range(frames):
        p = fi / (frames - 1)
        img = bg()
        put_glow(img, acc, 300 + 60 * math.sin(p * 2 * PI), 80 + 40 * math.sin(p * 2 * PI + 1.2), 700)
        put_glow(img, acc, 1020 + 40 * math.sin(p * 2 * PI + 2.0), 620 + 30 * math.cos(p * 2 * PI), 760)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        particles(d, p, acc)
        scene(d, p)
        footer(d, p, acc)
        out = Image.alpha_composite(img, layer)
        fade = min(1.0, p / 0.055, (1 - p) / 0.06)
        if fade < 1:
            out = Image.blend(BLACK, out, max(0.0, fade))
        out.convert("RGB").save(os.path.join(TMP, "f_%04d.png" % fi))

    path = os.path.join(OUT, name + ".mp4")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(TMP, "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium",
        "-movflags", "+faststart", path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(TMP, ignore_errors=True)
    return path, os.path.getsize(path) // 1024


if __name__ == "__main__":
    import sys
    only = sys.argv[1:] or None
    for name, (sec, acc, sc) in SCENES.items():
        if only and name not in only:
            continue
        p, kb = render(name, sec, acc, sc)
        print(p, kb, "KB")
