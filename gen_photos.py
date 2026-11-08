from PIL import Image, ImageDraw, ImageFont
import os

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
ACCENT = (182, 255, 62)


def font(size, weight=700):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def bg(w, h):
    strip = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(strip)
    for y in range(h):
        d.point((0, y), fill=lerp(DARK_TOP, DARK_BOT, y / max(1, h - 1)))
    img = strip.resize((w, h), Image.BILINEAR)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 60):
        d.line([(x, 0), (x, h)], fill=GRID, width=1)
    for y in range(0, h, 60):
        d.line([(0, y), (w, y)], fill=GRID, width=1)
    return img


def rr(d, box, r, fill=None, outline=None, width=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def save(img, name):
    p = os.path.join(ASSETS, name)
    img.save(p, quality=95)
    img.save(os.path.join(OUT, name), quality=95)
    print(name, os.path.getsize(p) // 1024)


def intro_photo():
    W, H = 1280, 720
    img = bg(W, H)
    d = ImageDraw.Draw(img)

    d.text((72, 70), "ПОРТФОЛИО", font=font(26, 600), fill=ACCENT)
    d.rectangle([72, 108, 210, 112], fill=ACCENT)

    d.text((68, 190), "САЙТЫ", font=font(132, 800), fill=WHITE)
    d.text((68, 330), "И БОТЫ", font=font(132, 800), fill=ACCENT)
    d.text((72, 510), "под задачу · примеры внутри · цена и срок заранее", font=font(28, 400), fill=MUTED)

    # right side: mini cards
    rx = 860
    items = [("Боты", (182, 255, 62)), ("Сайты", (255, 138, 61)), ("Под задачу", (76, 215, 240))]
    for i, (t, acc) in enumerate(items):
        y = 170 + i * 150
        rr(d, [rx, y, W - 72, y + 120], 20, fill=(20, 26, 34), outline=(38, 46, 58), width=2)
        d.ellipse([rx + 22, y + 38, rx + 58, y + 74], fill=acc)
        d.text((rx + 76, y + 38), t, font=font(34, 700), fill=WHITE)
        d.rounded_rectangle([rx + 76, y + 82, rx + 220, y + 90], radius=4, fill=(56, 66, 82))

    save(img, "intro.jpg")


def section_photo(name, tag, title, sub, acc, motif):
    W, H = 1280, 720
    img = bg(W, H)
    d = ImageDraw.Draw(img)

    d.text((72, 70), tag, font=font(24, 600), fill=acc)
    d.rectangle([72, 106, 180, 110], fill=acc)
    d.text((68, 250), title, font=font(88, 800), fill=WHITE)
    # wrap sub
    words, line, lines = sub.split(), "", []
    for w in words:
        test = (line + " " + w).strip()
        if d.textbbox((0, 0), test, font=font(28, 400))[2] < 520:
            line = test
        else:
            lines.append(line); line = w
    if line:
        lines.append(line)
    yy = 370
    for ln in lines[:2]:
        d.text((72, yy), ln, font=font(28, 400), fill=MUTED)
        yy += 40

    motif(d, acc)
    save(img, name)


def m_catalog(d, acc):
    x, y = 860, 140
    for i in range(4):
        yy = y + i * 130
        rr(d, [x, yy, 1208, yy + 104], 18, fill=(20, 26, 34), outline=(38, 46, 58), width=2)
        rr(d, [x + 20, yy + 24, x + 56, yy + 60], 10, fill=acc)
        d.rounded_rectangle([x + 74, yy + 28, x + 240, yy + 40], radius=5, fill=(70, 82, 100))
        d.rounded_rectangle([x + 74, yy + 52, x + 170, yy + 62], radius=4, fill=acc)
        d.rounded_rectangle([x + 260, yy + 34, x + 320, yy + 70], radius=12, fill=(26, 33, 43), outline=(56, 66, 82), width=2)


def m_examples(d, acc):
    for k, (bx, col, lab) in enumerate([(860, acc, "БОТЫ"), (1040, (255, 138, 61), "САЙТЫ")]):
        rr(d, [bx, 150, bx + 160, 590], 18, fill=(18, 23, 31), outline=col, width=3)
        d.text((bx + 18, 172), lab, font=font(18, 700), fill=col)
        if k == 0:
            for i in range(3):
                rr(d, [bx + 16, 220 + i * 60, bx + 144, 220 + i * 60 + 42], 10, fill=(30, 37, 48))
            rr(d, [bx + 16, 410, bx + 144, 452], 10, fill=col)
        else:
            rr(d, [bx + 16, 220, bx + 144, 260], 8, fill=(30, 37, 48))
            rr(d, [bx + 16, 274, bx + 144, 350], 10, fill=col)
            rr(d, [bx + 16, 364, bx + 144, 430], 10, fill=(30, 37, 48))
            rr(d, [bx + 16, 444, bx + 90, 476], 10, fill=col)
        rr(d, [bx + 16, 540, bx + 144, 570], 8, fill=(26, 33, 43))


def m_custom(d, acc):
    x, y = 860, 160
    rr(d, [x, y, 1208, y + 420], 20, fill=(20, 26, 34), outline=(38, 46, 58), width=2)
    widths = [280, 220, 300, 180]
    for i, w in enumerate(widths):
        col = acc if i == 3 else (70, 82, 100)
        d.rounded_rectangle([x + 30, y + 50 + i * 72, x + 30 + w, y + 74 + i * 72], radius=8, fill=col)
    d.rectangle([x + 30, y + 338, x + 33, y + 362], fill=acc)


def m_contact(d, acc):
    rr(d, [860, 170, 1100, 280], 22, fill=(26, 33, 43), outline=(52, 62, 78), width=2)
    for i in range(3):
        d.ellipse([890 + i * 28, 214, 906 + i * 28, 230], fill=acc)
    rr(d, [930, 310, 1208, 430], 22, fill=acc)
    d.rounded_rectangle([964, 344, 1140, 360], radius=6, fill=(12, 16, 20))
    d.rounded_rectangle([964, 376, 1080, 390], radius=5, fill=(12, 16, 20))
    d.line([(980, 520), (1120, 520)], fill=acc, width=10)
    d.polygon([(1120, 504), (1150, 520), (1120, 536)], fill=acc)


def service_photos():
    import math
    W, H = 1280, 720
    services = [
        ("svc_zayavki.jpg", "БОТ ПРИЁМА ЗАЯВОК", "750 ₽ · 1–2 дня", (182, 255, 62),
         "Клиент пишет боту — заявка сразу падает вам в личку. Меню, кнопки, уведомления."),
        ("svc_zapis.jpg", "БОТ ЗАПИСИ", "1 250 ₽ · 2–3 дня", (76, 215, 240),
         "Услуга, мастер, время. Напоминание за час. Клиенты записываются сами."),
        ("svc_site.jpg", "САЙТ-ВИЗИТКА", "500 ₽ · 2–4 дня", (255, 138, 61),
         "Услуги, цены, фото, форма заявки. Открывается с телефона, заявки в телеграм."),
        ("svc_menu.jpg", "МЕНЮ ПО QR", "750 ₽ · 1–2 дня", (61, 224, 160),
         "Для кафе и доставки: гость сканирует QR, видит меню и делает заказ без звонка."),
        ("svc_ai.jpg", "ИИ-БОТ", "2 000 ₽ · 3–5 дней", (106, 168, 255),
         "Отвечает клиентам по вашему прайсу и документам. Без вашего участия."),
        ("svc_custom.jpg", "СВОЙ ВАРИАНТ", "по задаче", (222, 228, 238),
         "Не нашли нужное? Опишите задачу — скажу, возьмусь или нет, и сколько стоит."),
    ]
    for name, title, price, acc, desc in services:
        img = bg(W, H)
        d = ImageDraw.Draw(img)
        d.text((72, 70), "УСЛУГА", font=font(24, 600), fill=acc)
        d.rectangle([72, 106, 170, 110], fill=acc)
        # title wrap
        words, line, lines = title.split(), "", []
        for w in words:
            test = (line + " " + w).strip()
            if d.textbbox((0, 0), test, font=font(72, 800))[2] < 760:
                line = test
            else:
                lines.append(line); line = w
        if line:
            lines.append(line)
        yy = 190
        for ln in lines[:2]:
            d.text((68, yy), ln, font=font(72, 800), fill=WHITE)
            yy += 84
        rr(d, [72, yy + 16, 360, yy + 76], 30, fill=(28, 36, 46), outline=acc, width=2)
        d.text((100, yy + 28), price, font=font(30, 700), fill=acc)
        # desc
        words, line, lines = desc.split(), "", []
        for w in words:
            test = (line + " " + w).strip()
            if d.textbbox((0, 0), test, font=font(24, 400))[2] < 760:
                line = test
            else:
                lines.append(line); line = w
        if line:
            lines.append(line)
        ty = yy + 110
        for ln in lines[:3]:
            d.text((72, ty), ln, font=font(24, 400), fill=MUTED)
            ty += 34
        # right accent block
        rr(d, [880, 150, 1208, 570], 24, fill=(18, 24, 31), outline=(38, 46, 58), width=2)
        d.rectangle([880, 150, 886, 570], fill=acc)
        # simple decorative lines
        for i in range(5):
            y = 210 + i * 64
            w = 240 - (i % 3) * 50
            d.rounded_rectangle([920, y, 920 + w, y + 14], radius=6, fill=(acc if i == 0 else (56, 66, 82)))
        save(img, name)


if __name__ == "__main__":
    intro_photo()
    section_photo("scr_catalog.jpg", "РАЗДЕЛ", "КАТАЛОГ", "5 услуг и свой вариант. Цена и срок у каждой.", (182, 255, 62), m_catalog)
    section_photo("scr_examples.jpg", "РАЗДЕЛ", "ПРИМЕРЫ", "8 сценариев: боты и сайты, можно посмотреть внутри.", (76, 215, 240), m_examples)
    section_photo("scr_custom.jpg", "РАЗДЕЛ", "СВОЙ ВАРИАНТ", "Опишите задачу — скажу, возьмусь или нет, и сколько стоит.", (222, 228, 238), m_custom)
    section_photo("scr_contact.jpg", "РАЗДЕЛ", "СВЯЗАТЬСЯ", "Напишите — отвечу быстро. Сообщение можно отправить в один клик.", (61, 224, 160), m_contact)
    service_photos()
