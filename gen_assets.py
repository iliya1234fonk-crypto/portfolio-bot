from PIL import Image, ImageDraw, ImageFont
import os

FONT = "/tmp/Onest.ttf"
OUT = "/storage/emulated/0/Download/portfolio-bot"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"
os.makedirs(OUT, exist_ok=True)
os.makedirs(ASSETS, exist_ok=True)

DARK_TOP = (11, 14, 19)
DARK_BOT = (19, 25, 33)
ACCENT = (182, 255, 62)
WHITE = (246, 248, 250)
MUTED = (138, 148, 166)
GRID = (24, 30, 38)


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(size, top, bottom):
    w, h = size
    strip = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(strip)
    for y in range(h):
        d.point((0, y), fill=lerp(top, bottom, y / max(1, h - 1)))
    return strip.resize((w, h), Image.BILINEAR)


def grid(d, size, step=64, color=GRID):
    w, h = size
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=color, width=1)


def center_text(d, cy, text, fnt, fill, width):
    box = d.textbbox((0, 0), text, font=fnt)
    w = box[2] - box[0]
    h = box[3] - box[1]
    d.text(((width - w) / 2 - box[0], cy - h / 2 - box[1]), text, font=fnt, fill=fill)


# ---------- аватарки (безопасные для круга) ----------
def avatar_monogram(dark=True):
    S = 1024
    if dark:
        img = vgrad((S, S), DARK_TOP, DARK_BOT)
        fg, acc, bg = WHITE, ACCENT, (23, 30, 39)
    else:
        img = Image.new("RGB", (S, S), (245, 241, 232))
        fg, acc, bg = (17, 19, 23), (222, 74, 40), (245, 241, 232)
    d = ImageDraw.Draw(img)
    grid(d, (S, S), 64, (24, 30, 38) if dark else (233, 227, 214))

    # кольцо по центру
    d.ellipse([152, 152, 872, 872], outline=acc if not dark else (44, 52, 64), width=4)

    # монограмма СБ
    f_big = font(330, 800)
    box = d.textbbox((0, 0), "СБ", font=f_big)
    w = box[2] - box[0]
    h = box[3] - box[1]
    x = (S - w) / 2 - box[0]
    y = (S - h) / 2 - box[1] - 30
    d.text((x, y), "СБ", font=f_big, fill=fg)

    # точка
    d.ellipse([x + w + 18, y + box[1] + h - 62, x + w + 78, y + box[1] + h - 2], fill=acc)

    name = "avatar-monogram-light.png" if not dark else "avatar-monogram.png"
    img.save(os.path.join(OUT, name))
    return img, name


def avatar_two_lines(dark=True):
    S = 1024
    if dark:
        img = vgrad((S, S), DARK_TOP, DARK_BOT)
        fg, acc, sub = WHITE, ACCENT, MUTED
    else:
        img = Image.new("RGB", (S, S), (245, 241, 232))
        fg, acc, sub = (17, 19, 23), (222, 74, 40), (110, 104, 92)
    d = ImageDraw.Draw(img)
    grid(d, (S, S), 64, (24, 30, 38) if dark else (233, 227, 214))

    center_text(d, 400, "САЙТЫ", font(150, 800), fg, S)
    center_text(d, 540, "И БОТЫ", font(150, 800), acc, S)

    d.rectangle([S / 2 - 180, 640, S / 2 + 180, 646], fill=acc)
    center_text(d, 700, "для бизнеса", font(52, 500), sub, S)

    name = "avatar-lines-light.png" if not dark else "avatar-lines.png"
    img.save(os.path.join(OUT, name))
    return img, name


# ---------- анимированная заставка ----------
def animated_intro():
    W, H = 1000, 560
    base = vgrad((W, H), DARK_TOP, DARK_BOT)
    d0 = ImageDraw.Draw(base)
    grid(d0, (W, H))

    full1 = "САЙТЫ"
    full2 = "И БОТЫ"
    f1 = font(128, 800)
    f2 = font(128, 800)
    f_sub = font(34, 400)
    f_tag = font(24, 600)

    d0.text((64, 54), "ПОРТФОЛИО", font=f_tag, fill=ACCENT)
    d0.rectangle([64, 92, 176, 96], fill=ACCENT)

    frames = []
    total = 9
    for i in range(total + 1):
        n1 = min(len(full1), i)
        n2 = max(0, min(len(full2), i - len(full1)))
        fr = base.copy()
        d = ImageDraw.Draw(fr)
        t1 = full1[:n1]
        t2 = full2[:n2]
        if t1:
            d.text((60, 180), t1, font=f1, fill=WHITE)
        if n1 >= len(full1) and t2:
            d.text((60, 300), t2, font=f2, fill=ACCENT)
        frames.append(fr)

    # финальные кадры
    for _ in range(3):
        fr = base.copy()
        d = ImageDraw.Draw(fr)
        d.text((60, 180), full1, font=f1, fill=WHITE)
        d.text((60, 300), full2, font=f2, fill=ACCENT)
        d.text((64, 470), "боты · сайты · заявки 24/7", font=f_sub, fill=MUTED)
        frames.append(fr)

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    durations = [70] * (len(pal) - 1) + [2500]
    path = os.path.join(ASSETS, "intro.gif")
    pal[0].save(
        path,
        save_all=True,
        append_images=pal[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    pal[-1].save(os.path.join(OUT, "intro-preview.png"))
    return path


if __name__ == "__main__":
    for d in (True, False):
        avatar_monogram(d)
        avatar_two_lines(d)
    p = animated_intro()
    print("gif:", p, os.path.getsize(p) // 1024, "KB")
    print(os.listdir(OUT))
