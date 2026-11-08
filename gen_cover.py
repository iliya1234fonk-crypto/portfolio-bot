from PIL import Image, ImageDraw, ImageFont
import os

FONT = "/tmp/Onest.ttf"
OUT = "/storage/emulated/0/Download/portfolio-bot"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"

os.makedirs(OUT, exist_ok=True)
os.makedirs(ASSETS, exist_ok=True)


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
    img = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.point((0, y), fill=lerp(top, bottom, y / max(1, h - 1)))
    return img.resize((w, h), Image.BILINEAR)


def grid(d, size, step=64, color=(24, 30, 38)):
    w, h = size
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=color, width=1)


def dark_cover():
    S = 1024
    img = vgrad((S, S), (11, 14, 19), (19, 25, 33))
    d = ImageDraw.Draw(img)
    grid(d, (S, S))

    accent = (182, 255, 62)
    white = (246, 248, 250)
    muted = (138, 148, 166)

    d.text((72, 74), "ПОРТФОЛИО", font=font(30, 600), fill=accent)
    d.rectangle([72, 120, 232, 124], fill=accent)

    d.text((66, 250), "САЙТЫ", font=font(196, 800), fill=white)
    d.text((66, 430), "И БОТЫ", font=font(196, 800), fill=accent)

    d.rectangle([72, 700, 952, 702], fill=(44, 52, 64))
    d.text((72, 748), "для малого бизнеса", font=font(58, 500), fill=white)
    d.text((72, 830), "собираю за 2–3 дня", font=font(44, 400), fill=muted)

    d.ellipse([880, 74, 952, 146], outline=accent, width=6)
    d.ellipse([907, 101, 925, 119], fill=accent)

    img.save(os.path.join(OUT, "avatar-dark.png"))
    img.save(os.path.join(ASSETS, "avatar.png"))
    return img


def light_cover():
    S = 1024
    img = Image.new("RGB", (S, S), (245, 241, 232))
    d = ImageDraw.Draw(img)
    grid(d, (S, S), 64, (233, 227, 214))

    ink = (17, 19, 23)
    accent = (222, 74, 40)

    d.text((72, 74), "ПОРТФОЛИО", font=font(30, 700), fill=accent)
    d.text((66, 250), "САЙТЫ", font=font(196, 800), fill=ink)
    d.text((66, 430), "И БОТЫ", font=font(196, 800), fill=ink)
    d.rectangle([72, 690, 600, 706], fill=accent)

    d.text((72, 748), "для малого бизнеса", font=font(58, 500), fill=ink)
    d.text((72, 830), "собираю за 2–3 дня", font=font(44, 400), fill=(110, 104, 92))

    d.rounded_rectangle([880, 74, 952, 146], radius=16, fill=accent)

    img.save(os.path.join(OUT, "avatar-light.png"))
    return img


def hero():
    W, H = 1280, 640
    img = vgrad((W, H), (11, 14, 19), (18, 24, 32))
    d = ImageDraw.Draw(img)
    grid(d, (W, H))

    accent = (182, 255, 62)
    white = (246, 248, 250)
    muted = (138, 148, 166)

    d.text((72, 62), "ПОРТФОЛИО", font=font(26, 600), fill=accent)
    d.rectangle([72, 104, 208, 108], fill=accent)

    d.text((66, 190), "САЙТЫ", font=font(150, 800), fill=white)
    d.text((66, 340), "И БОТЫ", font=font(150, 800), fill=accent)

    d.text((72, 520), "боты · сайты · заявки 24/7", font=font(36, 400), fill=muted)

    # правая часть — карточка с ценами
    card = [840, 150, 1208, 500]
    d.rounded_rectangle(card, radius=28, fill=(23, 30, 39), outline=(44, 52, 64), width=2)
    d.text((884, 196), "ОТ", font=font(24, 600), fill=muted)
    d.text((884, 226), "500 ₽", font=font(76, 800), fill=accent)
    d.text((884, 330), "бот под ключ", font=font(30, 500), fill=white)
    d.text((884, 376), "1–3 дня", font=font(28, 400), fill=muted)

    d.ellipse([1120, 190, 1176, 246], outline=accent, width=5)
    d.ellipse([1141, 211, 1155, 225], fill=accent)

    img.save(os.path.join(OUT, "hero.png"))
    img.save(os.path.join(ASSETS, "hero.png"))
    return img


if __name__ == "__main__":
    dark_cover()
    light_cover()
    hero()
    print("saved:")
    print(os.listdir(OUT))
    print(os.listdir(ASSETS))
