from PIL import Image, ImageDraw, ImageFont
import os
import math
import subprocess
import shutil

FONT = "/tmp/Onest.ttf"
ASSETS = "/storage/emulated/0/portfolio-bot/assets"
OUT = "/storage/emulated/0/Download/portfolio-bot"
TMP = "/data/data/cat.narezany.margycode/cache/tmp/opencode/vidframes"
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
GREEN = (182, 255, 62)

# 720p landscape for good quality
W, H = 1280, 720


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def rr(d, box, r, fill=None, outline=None, w=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


def bars(d, x, y, widths, color=BUBBLE_LINE, h=8, gap=10, r=4):
    for i, w in enumerate(widths):
        rr(d, [x, y + i * (h + gap), x + w, y + i * (h + gap) + h], r, fill=color)


def clamp(v):
    v = max(0.0, min(1.0, v))
    # smoothstep
    return v * v * (3 - 2 * v)


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
    rr(d, box, 22, fill=CARD, outline=CARD_LINE, w=2)
    x, y = box[0], box[1]
    d.text((x + 20, y + 16), title, font=font(22, 800), fill=WHITE)
    d.text((x + 20, y + 46), subtitle, font=font(14, 500), fill=MUTED)
    d.rectangle([x + 20, y + 68, x + 58, y + 71], fill=accent)


def chat_bubble(d, box, fill, lines, accent=None):
    rr(d, box, 16, fill=fill)
    if accent:
        d.rectangle([box[0], box[1] + 10, box[0] + 3, box[3] - 10], fill=accent)
    bars(d, box[0] + 14, box[1] + 13, lines, color=BUBBLE_LINE, h=7, gap=8)


def typing(d, x, y, accent, phase):
    for i in range(3):
        on = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(phase * 6.28 - i * 0.9))
        col = tuple(int(c * on) for c in accent)
        d.ellipse([x + i * 14, y, x + i * 14 + 8, y + 8], fill=col)


def kb_button(d, box, label, accent, filled=False, press=False):
    if press:
        rr(d, box, 10, fill=accent)
        col = (10, 14, 18)
    elif filled:
        rr(d, box, 10, fill=(26, 33, 43), outline=accent, w=2)
        col = accent
    else:
        rr(d, box, 10, fill=(26, 33, 43), outline=(56, 66, 82), w=2)
        col = WHITE
    f = font(14, 600)
    tw = d.textbbox((0, 0), label, font=f)[2]
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + 7), label, font=f, fill=col)


def bot_panel(d, box, title, sub, accent, scenario, p, ph):
    panel(d, box, title, sub, accent)
    x, y, x2, y2 = box
    cx, cw = x + 18, x2 - x - 36
    top = y + 84

    if p > 0.06:
        chat_bubble(d, [cx, top, cx + cw * 0.78, top + 58], BUBBLE,
                    [cw * 0.62, cw * 0.5, cw * 0.35], accent=accent)
    if 0.10 <= p < 0.30:
        typing(d, cx + 18, top + 68, accent, ph)

    by = top + 80
    for i, label in enumerate(scenario[:3]):
        step = 0.30 + i * 0.10
        if p >= step:
            press = i == 0 and p >= 0.66
            kb_button(d, [cx, by + i * 38, cx + cw * 0.62, by + i * 38 + 30],
                      label, accent, filled=(i == 0), press=press)

    uy = by + len(scenario[:3]) * 38 + 10
    if p > 0.72:
        chat_bubble(d, [cx + cw * 0.32, uy, cx + cw, uy + 38],
                    (32, 36, 46), [cw * 0.5], accent=accent)

    cy = uy + 50
    if p > 0.86 and cy + 50 < y2 - 12:
        rr(d, [cx, cy, cx + cw, cy + 48], 14, fill=(22, 30, 26))
        d.text((cx + 14, cy + 8), "Готово", font=font(15, 700), fill=accent)
        bars(d, cx + 14, cy + 30, [cw * 0.55], color=(52, 64, 56), h=6, gap=6)


def site_panel(d, box, title, sub, accent, headline, tag, p):
    panel(d, box, title, sub, accent)
    x, y, x2, y2 = box
    bx, by = x + 18, y + 84
    bw, bh = x2 - x - 36, y2 - y - 100

    rr(d, [bx, by, bx + bw, by + bh], 14, fill=(16, 21, 28), outline=(44, 52, 64), w=2)
    if p > 0.04:
        d.line([(bx, by + 28), (bx + bw, by + 28)], fill=(44, 52, 64), width=2)
        for i in range(3):
            d.ellipse([bx + 12 + i * 14, by + 10, bx + 18 + i * 14, by + 16], fill=(70, 80, 96))
        rr(d, [bx + 60, by + 6, bx + bw - 10, by + 22], 8, fill=(26, 33, 43))
        d.text((bx + 70, by + 8), tag, font=font(11, 500), fill=MUTED)
    if p > 0.18:
        d.text((bx + 16, by + 44), headline, font=font(24, 800), fill=WHITE)
    if p > 0.28:
        bars(d, bx + 16, by + 80, [bw * 0.62, bw * 0.44], color=(60, 70, 86), h=7, gap=8)
    if p > 0.42:
        kb_button(d, [bx + 16, by + 114, bx + 118, by + 144], "Заказать", accent, filled=True, press=p > 0.74)
    if p > 0.50:
        kb_button(d, [bx + 128, by + 114, bx + 224, by + 144], "Подробнее", accent)
    iy = by + 160
    if p > 0.60 and iy + 70 < by + bh - 8:
        rr(d, [bx + 16, iy, bx + bw - 16, iy + 66], 12, fill=(24, 31, 40))
        mid = bx + 16 + (bw - 32) / 2
        d.ellipse([mid - 14, iy + 19, mid + 14, iy + 47], outline=accent, width=3)
    cy = iy + 78
    cw = (bw - 44) / 2
    if p > 0.76 and cy + 40 < by + bh - 8:
        for i in range(2):
            ccx = bx + 16 + i * (cw + 12)
            rr(d, [ccx, cy, ccx + cw, cy + 38], 8, fill=(24, 31, 40))
            bars(d, ccx + 8, cy + 10, [cw * 0.6, cw * 0.4], color=(56, 66, 82), h=5, gap=5)


BOTS = [
    ("Бот записи", "салон · услуга, мастер, время", (182, 255, 62), ["Маникюр", "Педикюр", "Записаться"]),
    ("Бот заявок", "магазин · заявка в личку", (76, 215, 240), ["Каталог", "Оставить заявку", "Позвонить"]),
    ("Меню по QR", "кафе · заказ без звонка", (255, 138, 61), ["Меню", "Заказать", "Адрес"]),
    ("ИИ-бот", "ответы по прайсу 24/7", (61, 224, 160), ["Цены", "Сроки", "Связаться"]),
]

SITES = [
    ("Сайт-визитка", "мастер · услуги и запись", (255, 138, 61), "Маникюр", "master.ru"),
    ("Лендинг", "ремонт · заявка в телеграм", (182, 255, 62), "Ремонт", "remont.ru"),
    ("Портфолио", "фотограф · работы и связь", (76, 215, 240), "Съёмка", "photo.ru"),
    ("Каталог", "цветы · витрина без оплаты", (61, 224, 160), "Букеты", "flowers.ru"),
]

# 4 panels on 1280x720
PAD, TOP = 24, 118
PW = (W - PAD * 3) // 2
PH = (H - TOP - PAD * 2) // 2
BOXES = [
    [PAD, TOP, PAD + PW, TOP + PH],
    [PAD * 2 + PW, TOP, PAD * 2 + PW * 2, TOP + PH],
    [PAD, TOP + PH + PAD, PAD + PW, TOP + PH * 2 + PAD],
    [PAD * 2 + PW, TOP + PH + PAD, PAD * 2 + PW * 2, TOP + PH * 2 + PAD],
]


def render_video(name, kind, title, sub, accent, seconds=11, fps=30):
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    frames = seconds * fps
    step = 0.06
    for fi in range(frames):
        p = fi / (frames - 1)
        img, d = canvas()
        header(d, title, sub, accent)
        for k in range(4):
            lp = clamp((p - k * step) / 0.38)
            if kind == "bots":
                t, s, acc, scen = BOTS[k]
                bot_panel(d, BOXES[k], t, s, acc, scen, lp, p + k * 0.25)
            else:
                t, s, acc, head, tag = SITES[k]
                site_panel(d, BOXES[k], t, s, acc, head, tag, lp)
        img.save(os.path.join(TMP, f"f_{fi:04d}.png"))

    out = os.path.join(ASSETS, name)
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(TMP, "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "22", "-preset", "medium",
        "-movflags", "+faststart",
        out,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(TMP, ignore_errors=True)
    return out, os.path.getsize(out) // 1024


def render_trust(seconds=12, fps=30):
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    frames = seconds * fps
    steps = [
        ("1. Обсуждаем задачу", "Пишете, что нужно — называю цену и срок до начала работы.", (76, 215, 240)),
        ("2. Показываю результат", "Сначала смотрите демо. Оплата — после того, как увидели, что всё работает.", (182, 255, 62)),
        ("3. Передаю и помогаю", "Отдаю доступ и исходники. Мелкие правки по задаче делаю сразу.", (255, 138, 61)),
        ("4. На связи", "Отвечаю в телеграме. Если что-то сломалось по моей части — чиним.", (61, 224, 160)),
    ]
    for fi in range(frames):
        p = fi / (frames - 1)
        img, d = canvas()
        header(d, "КАК Я РАБОТАЮ", "понятные условия, без сюрпризов", GREEN)
        # left: process steps
        lx, ly = 48, 130
        for i, (title, desc, acc) in enumerate(steps):
            sp = clamp((p - i * 0.10) / 0.18)
            if sp <= 0:
                continue
            yy = ly + i * 136
            # highlight current
            cur = i <= int(p * 4.6)
            if cur:
                rr(d, [lx, yy, lx + 560, yy + 118], 18, fill=(18, 24, 20), outline=acc, w=2)
            d.ellipse([lx + 18, yy + 16, lx + 46, yy + 44], fill=acc if cur else (46, 56, 70))
            num = font(16, 800)
            nw = d.textbbox((0, 0), str(i + 1), font=num)[2]
            d.text((lx + 32 - nw / 2, yy + 21), str(i + 1), font=num, fill=(10, 14, 18))
            d.text((lx + 60, yy + 16), title, font=font(21, 800), fill=WHITE)
            # wrap desc
            words, line, lines = desc.split(), "", []
            for w in words:
                test = (line + " " + w).strip()
                if d.textbbox((0, 0), test, font=font(15, 400))[2] < 460:
                    line = test
                else:
                    lines.append(line); line = w
            if line:
                lines.append(line)
            ty = yy + 48
            for ln in lines[:2]:
                d.text((lx + 60, ty), ln, font=font(15, 400), fill=MUTED)
                ty += 22

        # right: proof cards
        rx = 660
        proofs = [
            ("Примеры в боте", "8 готовых сценариев: боты и сайты, можно открыть и посмотреть.", (76, 215, 240)),
            ("Демо до оплаты", "Сначала показываю работающий результат, потом решаете.", (182, 255, 62)),
            ("Честно по задаче", "Если задача не моя — скажу сразу, не буду тянуть время.", (255, 138, 61)),
        ]
        for i, (t, desc, acc) in enumerate(proofs):
            sp = clamp((p - 0.12 - i * 0.12) / 0.18)
            if sp <= 0:
                continue
            yy = 130 + i * 186
            rr(d, [rx, yy, W - 48, yy + 162], 18, fill=CARD, outline=CARD_LINE, w=2)
            d.rectangle([rx + 22, yy + 22, rx + 26, yy + 54], fill=acc)
            d.text((rx + 38, yy + 22), t, font=font(20, 800), fill=WHITE)
            words, line, lines = desc.split(), "", []
            for w in words:
                test = (line + " " + w).strip()
                if d.textbbox((0, 0), test, font=font(14, 400))[2] < 500:
                    line = test
                else:
                    lines.append(line); line = w
            if line:
                lines.append(line)
            ty = yy + 58
            for ln in lines[:3]:
                d.text((rx + 22, ty), ln, font=font(14, 400), fill=MUTED)
                ty += 22

        img.save(os.path.join(TMP, f"f_{fi:04d}.png"))

    out = os.path.join(ASSETS, "trust.mp4")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(TMP, "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "22", "-preset", "medium",
        "-movflags", "+faststart",
        out,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(TMP, ignore_errors=True)
    return out, os.path.getsize(out) // 1024


if __name__ == "__main__":
    print("bots", render_video("examples_bots.mp4", "bots", "ПРИМЕРЫ · БОТЫ", "4 сценария, которые собираю под задачу", (182, 255, 62)))
    print("sites", render_video("examples_sites.mp4", "sites", "ПРИМЕРЫ · САЙТЫ", "4 макета, которые собираю под задачу", (255, 138, 61)))
    print("trust", render_trust())
