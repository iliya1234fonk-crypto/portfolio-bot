from PIL import Image, ImageDraw, ImageFont
import os

FONT = "/tmp/Onest.ttf"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"
OUT = "/storage/emulated/0/Download/portfolio-bot"
os.makedirs(ASSETS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

BG = (11, 14, 19)
GRIDC = (20, 25, 33)
CARD = (20, 26, 34)
CARD_LINE = (34, 42, 54)
WHITE = (246, 248, 250)
MUTED = (138, 148, 166)
BUBBLE = (30, 37, 48)
BUBBLE_LINE = (58, 68, 84)


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def rr(d, box, r, fill=None, outline=None, w=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


def bars(d, x, y, widths, color=BUBBLE_LINE, h=9, gap=11, r=4):
    for i, w in enumerate(widths):
        rr(d, [x, y + i * (h + gap), x + w, y + i * (h + gap) + h], r, fill=color)


def clamp(v):
    return max(0.0, min(1.0, v))


def tile(d, box, title, subtitle, accent):
    rr(d, box, 26, fill=CARD, outline=CARD_LINE, w=2)
    x, y, x2, y2 = box
    d.text((x + 26, y + 22), title, font=font(27, 800), fill=WHITE)
    d.text((x + 26, y + 58), subtitle, font=font(16, 500), fill=MUTED)
    d.rectangle([x + 26, y + 84, x + 26 + 46, y + 87], fill=accent)


def chat_bubble(d, box, fill, lines, accent=None):
    rr(d, box, 18, fill=fill)
    if accent:
        d.rectangle([box[0], box[1] + 12, box[0] + 3, box[3] - 12], fill=accent)
    bars(d, box[0] + 18, box[1] + 16, lines, color=BUBBLE_LINE)


def typing(d, x, y, accent, phase):
    for i in range(3):
        on = 0.35 + 0.65 * (0.5 + 0.5 * __import__("math").sin(phase * 3.14 * 2 - i * 0.9))
        col = tuple(int(c * on) for c in accent)
        d.ellipse([x + i * 16, y, x + i * 16 + 9, y + 9], fill=col)


def kb_button(d, box, label, accent, filled=False, press=False):
    if press:
        rr(d, box, 12, fill=accent)
        col = (10, 14, 18)
    elif filled:
        rr(d, box, 12, fill=(26, 33, 43), outline=accent, w=2)
        col = accent
    else:
        rr(d, box, 12, fill=(26, 33, 43), outline=(56, 66, 82), w=2)
        col = WHITE
    f = font(17, 600)
    tw = d.textbbox((0, 0), label, font=f)[2]
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + 9), label, font=f, fill=col)


def bot_tile(img, box, title, subtitle, accent, scenario, p, ph):
    d = ImageDraw.Draw(img)
    tile(d, box, title, subtitle, accent)
    x, y, x2, y2 = box
    cx = x + 22
    cw = x2 - x - 22
    top = y + 102

    if p > 0.06:
        chat_bubble(d, [cx, top, cx + cw * 0.78, top + 74], BUBBLE,
                    [cw * 0.62, cw * 0.5, cw * 0.35], accent=accent)

    if 0.10 <= p < 0.30:
        typing(d, cx + 22, top + 90, accent, ph)

    by = top + 112
    for i, label in enumerate(scenario[:3]):
        step = 0.30 + i * 0.11
        if p >= step:
            press = i == 0 and p >= 0.66
            kb_button(d, [cx, by + i * 44, cx + cw * 0.6, by + i * 44 + 36],
                      label, accent, filled=(i == 0), press=press)

    uy = by + len(scenario[:3]) * 44 + 12
    if p > 0.72:
        green = accent[1] > 200
        chat_bubble(d, [cx + cw * 0.3, uy, cx + cw, uy + 46],
                    (30, 42, 34) if green else (32, 36, 46), [cw * 0.5], accent=accent)

    cy = uy + 60
    if p > 0.86 and cy + 62 < y2 - 16:
        rr(d, [cx, cy, cx + cw, cy + 62], 16, fill=(22, 30, 26))
        d.text((cx + 18, cy + 10), "Готово", font=font(18, 700), fill=accent)
        bars(d, cx + 18, cy + 38, [cw * 0.55], color=(52, 64, 56), h=8, gap=8)


def site_tile(img, box, title, subtitle, accent, headline, tag, p):
    d = ImageDraw.Draw(img)
    tile(d, box, title, subtitle, accent)
    x, y, x2, y2 = box
    bx, by = x + 22, y + 102
    bw, bh = x2 - x - 44, y2 - y - 124

    rr(d, [bx, by, bx + bw, by + bh], 16, fill=(16, 21, 28), outline=(44, 52, 64), w=2)
    if p > 0.04:
        d.line([(bx, by + 34), (bx + bw, by + 34)], fill=(44, 52, 64), width=2)
        for i in range(3):
            d.ellipse([bx + 14 + i * 16, by + 12, bx + 22 + i * 16, by + 20], fill=(70, 80, 96))
        rr(d, [bx + 70, by + 8, bx + bw - 14, by + 26], 9, fill=(26, 33, 43))
        d.text((bx + 82, by + 11), tag, font=font(13, 500), fill=MUTED)

    if p > 0.18:
        d.text((bx + 22, by + 58), headline, font=font(30, 800), fill=WHITE)
    if p > 0.28:
        bars(d, bx + 22, by + 104, [bw * 0.62, bw * 0.44], color=(60, 70, 86), h=8, gap=9)

    if p > 0.42:
        kb_button(d, [bx + 22, by + 146, bx + 150, by + 182], "Заказать", accent, filled=True,
                  press=p > 0.74)
    if p > 0.50:
        kb_button(d, [bx + 162, by + 146, bx + 280, by + 182], "Подробнее", accent)

    iy = by + 210
    if p > 0.60 and iy + 96 < by + bh - 10:
        rr(d, [bx + 22, iy, bx + bw - 22, iy + 96], 14, fill=(24, 31, 40))
        mid = bx + 22 + (bw - 44) / 2
        d.ellipse([mid - 16, iy + 32, mid + 16, iy + 64], outline=accent, width=4)

    cy = iy + 110
    cw = (bw - 60) / 2
    if p > 0.74:
        for i in range(2):
            ccx = bx + 22 + i * (cw + 16)
            if cy + 46 < by + bh - 12:
                rr(d, [ccx, cy, ccx + cw, cy + 46], 10, fill=(24, 31, 40))
                bars(d, ccx + 10, cy + 12, [cw * 0.6, cw * 0.4], color=(56, 66, 82), h=6, gap=6)

    fy = cy + 60
    if p > 0.86 and fy + 30 < by + bh - 8:
        d.line([(bx + 22, fy - 10), (bx + bw - 22, fy - 10)], fill=(36, 44, 56), width=1)
        colw = (bw - 60) / 3
        for i in range(3):
            fx = bx + 22 + i * (colw + 8)
            bars(d, fx, fy, [colw * 0.7, colw * 0.45], color=(48, 58, 72), h=5, gap=6)


def canvas():
    W, H = 1200, 1320
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 60):
        d.line([(gx, 0), (gx, H)], fill=GRIDC, width=1)
    for gy in range(0, H, 60):
        d.line([(0, gy), (W, gy)], fill=GRIDC, width=1)
    return img, d


def header(d, title, sub, accent):
    d.text((56, 46), title, font=font(30, 700), fill=accent)
    d.text((56, 86), sub, font=font(20, 400), fill=MUTED)
    d.rectangle([56, 124, 176, 128], fill=accent)


BOTS = [
    ("Бот записи", "салон красоты · услуга, мастер, время", (182, 255, 62), ["Маникюр", "Педикюр", "Записаться"]),
    ("Бот заявок", "магазин · заявка сразу в личку", (76, 215, 240), ["Каталог", "Оставить заявку", "Позвонить"]),
    ("Меню по QR", "кафе · меню и заказ без звонка", (255, 138, 61), ["Меню", "Заказать", "Адрес"]),
    ("ИИ-бот", "отвечает по вашему прайсу 24/7", (61, 224, 160), ["Цены", "Сроки", "Связаться"]),
]

SITES = [
    ("Сайт-визитка", "мастер маникюра · услуги и запись", (255, 138, 61), "Маникюр", "master.ru"),
    ("Лендинг", "ремонт квартир · заявка в телеграм", (182, 255, 62), "Ремонт", "remont.ru"),
    ("Портфолио", "фотограф · работы и связь", (76, 215, 240), "Съёмка", "photo.ru"),
    ("Каталог", "цветы · витрина без оплаты", (61, 224, 160), "Букеты", "flowers.ru"),
]

BOXES = [
    [56, 160, 588, 720],
    [612, 160, 1144, 720],
    [56, 752, 588, 1312],
    [612, 752, 1144, 1312],
]


def render(kind, accent, title, sub, frames=20):
    out = []
    step = 0.09
    for fi in range(frames):
        p = fi / (frames - 1)
        img, d = canvas()
        header(d, title, sub, accent)
        for k in range(4):
            lp = clamp((p - k * step) / 0.52)
            if kind == "bots":
                t, s, acc, scen = BOTS[k]
                bot_tile(img, BOXES[k], t, s, acc, scen, lp, p + k * 0.25)
            else:
                t, s, acc, head, tag = SITES[k]
                site_tile(img, BOXES[k], t, s, acc, head, tag, lp)
        out.append(img)

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in out]
    durations = [90] * (len(pal) - 1) + [2400]
    name = "examples_bots.gif" if kind == "bots" else "examples_sites.gif"
    path = os.path.join(ASSETS, name)
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    pal[-1].save(os.path.join(OUT, name.replace(".gif", "-preview.png")))
    return path, os.path.getsize(path) // 1024


if __name__ == "__main__":
    print(render("bots", (182, 255, 62), "ПРИМЕРЫ · БОТЫ", "4 сценария, которые собираю за пару дней"))
    print(render("sites", (255, 138, 61), "ПРИМЕРЫ · САЙТЫ", "4 макета, которые собираю за пару дней"))
