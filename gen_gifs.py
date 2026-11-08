from PIL import Image, ImageDraw, ImageFont
import os

FONT = "/tmp/Onest.ttf"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"
os.makedirs(ASSETS, exist_ok=True)

DARK_TOP = (11, 14, 19)
DARK_BOT = (19, 25, 33)
GRID = (24, 30, 38)
WHITE = (246, 248, 250)
MUTED = (138, 148, 166)


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


def grid(d, size, step=48, color=GRID):
    w, h = size
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=color, width=1)


def make_gif(filename, title, sub, accent, label="ПОРТФОЛИО"):
    W, H = 900, 380
    base = vgrad((W, H), DARK_TOP, DARK_BOT)
    d0 = ImageDraw.Draw(base)
    grid(d0, (W, H))

    # подбираем размер шрифта под ширину
    size = 120
    while size > 40:
        f = font(size, 800)
        box = d0.textbbox((0, 0), title, font=f)
        if (box[2] - box[0]) < W - 150:
            break
        size -= 6
    ftitle = font(size, 800)
    fsub = font(28, 400)
    flag = font(20, 700)

    tw = d0.textbbox((0, 0), title, font=ftitle)
    text_w = tw[2] - tw[0]
    underline_y = 250

    frames = []
    steps = 8
    for i in range(steps + 1):
        n = max(1, int(len(title) * i / steps)) if i else 0
        fr = base.copy()
        d = ImageDraw.Draw(fr)
        d.text((60, 34), label, font=flag, fill=accent)
        d.rectangle([60, 60, 160, 64], fill=accent)
        d.text((60, 120), title[:n], font=ftitle, fill=WHITE)
        frames.append(fr)

    for _ in range(2):
        fr = base.copy()
        d = ImageDraw.Draw(fr)
        d.text((60, 34), label, font=flag, fill=accent)
        d.rectangle([60, 60, 160, 64], fill=accent)
        d.text((60, 120), title, font=ftitle, fill=WHITE)
        d.rectangle([60, underline_y, 60 + text_w, underline_y + 6], fill=accent)
        if sub:
            d.text((62, 280), sub, font=fsub, fill=MUTED)
        frames.append(fr)

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=48) for f in frames]
    path = os.path.join(ASSETS, filename)
    pal[0].save(path, save_all=True, append_images=pal[1:],
                duration=[60] * (len(pal) - 1) + [1800], loop=0, optimize=True)
    return path, os.path.getsize(path) // 1024


if __name__ == "__main__":
    items = [
        ("g_bots.gif", "БОТЫ", "приём заявок · запись · модерация", (182, 255, 62)),
        ("g_sites.gif", "САЙТЫ", "визитка · лендинг · меню по QR", (90, 200, 255)),
        ("g_shop.gif", "КУПИТЬ", "выбери готовое решение", (255, 150, 60)),
        ("g_custom.gif", "СВОЙ ВАРИАНТ", "расскажи задачу — предложу решение", (185, 150, 255)),
        ("g_contact.gif", "СВЯЗАТЬСЯ", "отвечаю быстро", (120, 255, 200)),
    ]
    for fn, t, s, a in items:
        p, kb = make_gif(fn, t, s, a)
        print(fn, kb, "KB")
