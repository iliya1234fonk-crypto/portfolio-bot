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
W, H = 1280, 720


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def rr(d, box, r, fill=None, outline=None, width=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def bars(d, x, y, widths, color=(58, 68, 84), h=8, gap=10, r=4):
    for i, w in enumerate(widths):
        rr(d, [x, y + i * (h + gap), x + w, y + i * (h + gap) + h], r, fill=color)


def canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 48):
        d.line([(gx, 0), (gx, H)], fill=GRIDC, width=1)
    for gy in range(0, H, 48):
        d.line([(0, gy), (W, gy)], fill=GRIDC, width=1)
    return img, d


def header(d, title, sub, accent):
    d.text((48, 34), title, font=font(28, 700), fill=accent)
    d.text((48, 70), sub, font=font(18, 400), fill=MUTED)
    d.rectangle([48, 102, 148, 105], fill=accent)


def panel(d, box, title, subtitle, accent):
    rr(d, box, 22, fill=CARD, outline=CARD_LINE, width=2)
    x, y = box[0], box[1]
    d.text((x + 20, y + 16), title, font=font(22, 800), fill=WHITE)
    d.text((x + 20, y + 46), subtitle, font=font(14, 500), fill=MUTED)
    d.rectangle([x + 20, y + 68, x + 58, y + 71], fill=accent)


def chat_bubble(d, box, fill, lines, accent=None):
    rr(d, box, 16, fill=fill)
    if accent:
        d.rectangle([box[0], box[1] + 10, box[0] + 3, box[3] - 10], fill=accent)
    bars(d, box[0] + 14, box[1] + 13, lines, color=(58, 68, 84), h=7, gap=8)


def kb_button(d, box, label, accent, filled=False, press=False):
    if press:
        rr(d, box, 10, fill=accent); col = (10, 14, 18)
    elif filled:
        rr(d, box, 10, fill=(26, 33, 43), outline=accent, width=2); col = accent
    else:
        rr(d, box, 10, fill=(26, 33, 43), outline=(56, 66, 82), width=2); col = WHITE
    f = font(14, 600)
    tw = d.textbbox((0, 0), label, font=f)[2]
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + 7), label, font=f, fill=col)


PAD, TOP = 24, 118
PW = (W - PAD * 3) // 2
PH = (H - TOP - PAD * 2) // 2
BOXES = [
    [PAD, TOP, PAD + PW, TOP + PH],
    [PAD * 2 + PW, TOP, PAD * 2 + PW * 2, TOP + PH],
    [PAD, TOP + PH + PAD, PAD + PW, TOP + PH * 2 + PAD],
    [PAD * 2 + PW, TOP + PH + PAD, PAD * 2 + PW * 2, TOP + PH * 2 + PAD],
]


def bot_panel(d, box, title, sub, accent, scenario):
    panel(d, box, title, sub, accent)
    x, y, x2, y2 = box
    cx, cw = x + 18, x2 - x - 36
    top = y + 84
    chat_bubble(d, [cx, top, cx + cw * 0.78, top + 58], (30, 37, 48), [cw * 0.62, cw * 0.5, cw * 0.35], accent=accent)
    by = top + 80
    for i, label in enumerate(scenario[:3]):
        kb_button(d, [cx, by + i * 38, cx + cw * 0.62, by + i * 38 + 30], label, accent, filled=(i == 0), press=(i == 0))
    uy = by + len(scenario[:3]) * 38 + 10
    chat_bubble(d, [cx + cw * 0.32, uy, cx + cw, uy + 38], (32, 36, 46), [cw * 0.5], accent=accent)
    cy = uy + 50
    if cy + 48 < y2 - 12:
        rr(d, [cx, cy, cx + cw, cy + 48], 14, fill=(22, 30, 26))
        d.text((cx + 14, cy + 8), "Готово", font=font(15, 700), fill=accent)
        bars(d, cx + 14, cy + 30, [cw * 0.55], color=(52, 64, 56), h=6, gap=6)


def site_panel(d, box, title, sub, accent, headline, tag):
    panel(d, box, title, sub, accent)
    x, y, x2, y2 = box
    bx, by = x + 18, y + 84
    bw, bh = x2 - x - 36, y2 - y - 100
    rr(d, [bx, by, bx + bw, by + bh], 14, fill=(16, 21, 28), outline=(44, 52, 64), width=2)
    d.line([(bx, by + 28), (bx + bw, by + 28)], fill=(44, 52, 64), width=2)
    for i in range(3):
        d.ellipse([bx + 12 + i * 14, by + 10, bx + 18 + i * 14, by + 16], fill=(70, 80, 96))
    rr(d, [bx + 60, by + 6, bx + bw - 10, by + 22], 8, fill=(26, 33, 43))
    d.text((bx + 70, by + 8), tag, font=font(11, 500), fill=MUTED)
    d.text((bx + 16, by + 44), headline, font=font(24, 800), fill=WHITE)
    bars(d, bx + 16, by + 80, [bw * 0.62, bw * 0.44], color=(60, 70, 86), h=7, gap=8)
    kb_button(d, [bx + 16, by + 114, bx + 118, by + 144], "Заказать", accent, filled=True, press=True)
    kb_button(d, [bx + 128, by + 114, bx + 224, by + 144], "Подробнее", accent)
    iy = by + 160
    rr(d, [bx + 16, iy, bx + bw - 16, iy + 66], 12, fill=(24, 31, 40))
    mid = bx + 16 + (bw - 32) / 2
    d.ellipse([mid - 14, iy + 19, mid + 14, iy + 47], outline=accent, width=3)
    cy = iy + 78
    cw = (bw - 44) / 2
    for i in range(2):
        ccx = bx + 16 + i * (cw + 12)
        y1 = min(cy + 38, by + bh - 10)
        if y1 > cy + 8:
            rr(d, [ccx, cy, ccx + cw, y1], 8, fill=(24, 31, 40))
            bars(d, ccx + 8, cy + 10, [cw * 0.6, cw * 0.4], color=(56, 66, 82), h=5, gap=5)


def save(name):
    p = os.path.join(ASSETS, name)
    img.save(p, quality=95)
    print(name, os.path.getsize(p) // 1024)


# bots
BOTS = [
    ("Бот записи", "салон · услуга, мастер, время", (182, 255, 62), ["Маникюр", "Педикюр", "Записаться"]),
    ("Бот заявок", "магазин · заявка в личку", (76, 215, 240), ["Каталог", "Оставить заявку", "Позвонить"]),
    ("Меню по QR", "кафе · заказ без звонка", (255, 138, 61), ["Меню", "Заказать", "Адрес"]),
    ("ИИ-бот", "ответы по прайсу 24/7", (61, 224, 160), ["Цены", "Сроки", "Связаться"]),
]
img, d = canvas()
header(d, "ПРИМЕРЫ · БОТЫ", "4 сценария под задачу", (182, 255, 62))
for k, (t, s, acc, scen) in enumerate(BOTS):
    bot_panel(d, BOXES[k], t, s, acc, scen)
save("examples_bots.jpg")

# sites
SITES = [
    ("Сайт-визитка", "мастер · услуги и запись", (255, 138, 61), "Маникюр", "master.ru"),
    ("Лендинг", "ремонт · заявка в телеграм", (182, 255, 62), "Ремонт", "remont.ru"),
    ("Портфолио", "фотограф · работы и связь", (76, 215, 240), "Съёмка", "photo.ru"),
    ("Каталог", "цветы · витрина без оплаты", (61, 224, 160), "Букеты", "flowers.ru"),
]
img, d = canvas()
header(d, "ПРИМЕРЫ · САЙТЫ", "4 макета под задачу", (255, 138, 61))
for k, (t, s, acc, head, tag) in enumerate(SITES):
    site_panel(d, BOXES[k], t, s, acc, head, tag)
save("examples_sites.jpg")

# trust
GREEN = (182, 255, 62)
img, d = canvas()
header(d, "КАК Я РАБОТАЮ", "понятные условия, без сюрпризов", GREEN)
steps = [
    ("1. Обсуждаем задачу", "Называю цену и срок до начала работы.", (76, 215, 240)),
    ("2. Показываю демо", "Сначала смотрите результат, потом решаете по оплате.", (182, 255, 62)),
    ("3. Передаю всё", "Доступ и исходники остаются у вас.", (255, 138, 61)),
    ("4. На связи", "Отвечаю в телеграме, по моей части помогаю.", (61, 224, 160)),
]
lx = 48
for i, (title, desc, acc) in enumerate(steps):
    yy = 130 + i * 136
    rr(d, [lx, yy, lx + 560, yy + 118], 18, fill=(18, 24, 20), outline=acc, width=2)
    d.ellipse([lx + 18, yy + 16, lx + 46, yy + 44], fill=acc)
    nw = d.textbbox((0, 0), str(i + 1), font=font(16, 800))[2]
    d.text((lx + 32 - nw / 2, yy + 21), str(i + 1), font=font(16, 800), fill=(10, 14, 18))
    d.text((lx + 60, yy + 16), title, font=font(21, 800), fill=WHITE)
    d.text((lx + 60, yy + 52), desc, font=font(15, 400), fill=MUTED)
proofs = [
    ("Примеры в боте", "8 сценариев: боты и сайты. Можно открыть и посмотреть прямо здесь.", (76, 215, 240)),
    ("Демо до оплаты", "Сначала показываю работающий результат — решаете уже по делу.", (182, 255, 62)),
    ("Честно по задаче", "Если задача не моя — скажу сразу.", (255, 138, 61)),
]
rx = 660
for i, (t, desc, acc) in enumerate(proofs):
    yy = 130 + i * 186
    rr(d, [rx, yy, W - 48, yy + 162], 18, fill=CARD, outline=CARD_LINE, width=2)
    d.rectangle([rx + 22, yy + 22, rx + 26, yy + 54], fill=acc)
    d.text((rx + 38, yy + 22), t, font=font(20, 800), fill=WHITE)
    words, line, lines = desc.split(), "", []
    for w in words:
        test = (line + " " + w).strip()
        if d.textbbox((0, 0), test, font=font(14, 400))[2] < 500:
            line = test
        else:
            lines.append(line); line = w
    if line: lines.append(line)
    ty = yy + 58
    for ln in lines[:3]:
        d.text((rx + 22, ty), ln, font=font(14, 400), fill=MUTED); ty += 22
save("trust.jpg")
