from PIL import Image, ImageDraw, ImageFont
import os

FONT = "/tmp/Onest.ttf"
OUT = "/storage/emulated/0/Download/portfolio-bot"
os.makedirs(OUT, exist_ok=True)

S = 1024


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
        d.point((0, y), fill=lerp(top, bottom, y / (h - 1)))
    return strip.resize((w, h), Image.BILINEAR)


def grid(d, step=64, color=(233, 227, 214)):
    for x in range(0, S, step):
        d.line([(x, 0), (x, S)], fill=color, width=1)
    for y in range(0, S, step):
        d.line([(0, y), (S, y)], fill=color, width=1)


def center(d, cy, text, fnt, fill):
    box = d.textbbox((0, 0), text, font=fnt)
    w = box[2] - box[0]
    h = box[3] - box[1]
    d.text(((S - w) / 2 - box[0], cy - h / 2 - box[1]), text, font=fnt, fill=fill)


def build(light=True, subtitle="под любую задачу"):
    if light:
        img = Image.new("RGB", (S, S), (245, 241, 232))
        fg, acc, sub, gridc = (17, 19, 23), (222, 74, 40), (110, 104, 92), (233, 227, 214)
    else:
        img = vgrad((S, S), (11, 14, 19), (19, 25, 33))
        fg, acc, sub, gridc = (246, 248, 250), (182, 255, 62), (138, 148, 166), (24, 30, 38)

    d = ImageDraw.Draw(img)
    grid(d, 64, gridc)

    center(d, 400, "САЙТЫ", font(150, 800), fg)
    center(d, 540, "И БОТЫ", font(150, 800), acc)

    d.rectangle([S / 2 - 180, 640, S / 2 + 180, 646], fill=acc)
    center(d, 700, subtitle, font(52, 500), sub)

    name = "avatar-lines-light.png" if light else "avatar-lines.png"
    img.save(os.path.join(OUT, name))
    return os.path.join(OUT, name)


if __name__ == "__main__":
    print(build(True))
    print(build(False))
