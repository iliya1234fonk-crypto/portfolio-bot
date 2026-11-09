# -*- coding: utf-8 -*-
"""Генератор админ-инструкций v2: премиальный тёмный дизайн, авто-высота."""
import os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

F = "/tmp/Onest.ttf"
MONO = "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf"
OUT = "/storage/emulated/0/portfolio-bot/assets/guides"
os.makedirs(OUT, exist_ok=True)

W = 1400
M = 76
BG1 = (10, 13, 18)
BG2 = (17, 23, 32)
INK = (242, 246, 250)
DIM = (143, 154, 171)
MINT = (182, 255, 62)
CYAN = (86, 214, 240)
AMBER = (255, 150, 70)
GREEN = (72, 226, 160)
LINE = (35, 44, 57)


def fnt(size, w=400):
    f = ImageFont.truetype(F, size)
    try:
        f.set_variation_by_axes([w])
    except Exception:
        pass
    return f


def mono(size):
    return ImageFont.truetype(MONO, size)


def tracked(d, x, y, text, font, fill, sp):
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + sp
    return x


def tracked_w(text, font, sp):
    return sum(font.getlength(c) + sp for c in text)


def wrap(d, text, font, maxw):
    out = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
            continue
        cur = ""
        for wd in para.split():
            t = (cur + " " + wd).strip()
            if d.textlength(t, font=font) <= maxw:
                cur = t
            else:
                if cur:
                    out.append(cur)
                cur = wd
        if cur:
            out.append(cur)
    return out


def background(w, h):
    img = Image.new("RGB", (w, h), BG1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=(int(BG1[0] + (BG2[0] - BG1[0]) * t),
                                       int(BG1[1] + (BG2[1] - BG1[1]) * t),
                                       int(BG1[2] + (BG2[2] - BG1[2]) * t)))
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([-320, -420, 640, 420], fill=(17, 34, 12))
    g.ellipse([w - 620, h - 460, w + 260, h + 220], fill=(9, 22, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    return ImageChops.add(img, glow)


def header(d, badge, title, subtitle, accent=MINT):
    y = 64
    bw = tracked_w(badge, fnt(19, 700), 2.6) + 44
    d.rounded_rectangle([M, y, M + bw, y + 44], radius=22, outline=(46, 66, 40), width=2, fill=(18, 26, 18))
    d.ellipse([M + 16, y + 17, M + 26, y + 27], fill=accent)
    tracked(d, M + 36, y + 12, badge, fnt(19, 700), accent, 2.6)
    y += 76
    d.text((M - 3, y), title, font=fnt(62, 800), fill=INK)
    tw = d.textlength(title, font=fnt(62, 800))
    y += 82
    d.text((M, y), subtitle, font=fnt(26, 400), fill=DIM)
    y += 52
    d.line([(M, y), (W - M, y)], fill=LINE, width=2)
    d.line([(M, y), (M + 120, y)], fill=accent, width=3)
    return y + 44


def section(d, y, num, label, color):
    nf = fnt(28, 800)
    d.text((M, y - 4), num, font=nf, fill=color)
    x = M + d.textlength(num, font=nf) + 18
    lf = fnt(23, 700)
    x2 = tracked(d, x, y + 2, label, lf, (223, 231, 241), 3.0)
    d.line([(x2 + 22, y + 17), (W - M, y + 17)], fill=LINE, width=2)
    return y + 62


def measure_row(d, cmd, desc, dw=760):
    mf = mono(26)
    chip = d.textlength(cmd.split(" ")[0], font=mf)
    if len(cmd.split(" ")) > 1:
        chip += d.textlength(" " + cmd.split(" ", 1)[1], font=mf)
    lines = wrap(d, desc, fnt(23, 400), dw)
    return max(50, len(lines) * 32), len(lines)


def row(d, y, cmd, desc, color, dw=760):
    mf = mono(26) if cmd.startswith("/") else fnt(25, 700)
    parts = cmd.split(" ", 1)
    head = parts[0]
    tail = parts[1] if len(parts) > 1 else ""
    cw = d.textlength(head, font=mf) + (d.textlength(" " + tail, font=mf) if tail else 0)
    cw += 40
    d.rounded_rectangle([M, y, M + cw, y + 50], radius=13, fill=(22, 29, 39), outline=(38, 48, 62), width=2)
    d.rectangle([M + 6, y + 12, M + 9, y + 38], fill=color)
    d.text((M + 22, y + 9), head, font=mf, fill=color)
    if tail:
        d.text((M + 22 + d.textlength(head, font=mf), y + 9), " " + tail, font=mf, fill=(214, 222, 232))
    dx = M + 520
    lines = wrap(d, desc, fnt(23, 400), dw)
    yy = y + 9 if len(lines) == 1 else y + 4
    for ln in lines:
        d.text((dx, yy), ln, font=fnt(23, 400), fill=DIM)
        yy += 32
    return y + max(50, (yy - y)) + 14


def footer(w, h, page, total, accent=MINT):
    d = ImageDraw.Draw(img_global)
    y = h - 74
    d.line([(M, y), (W - M, y)], fill=LINE, width=2)
    d.text((M, y + 22), "Сайты и боты  ·  @portfoli_robot  ·  только для админов", font=fnt(20, 400), fill=(96, 106, 122))
    # dots
    cx = W - M
    for i in range(total):
        i = total - 1 - i
        c = accent if i == page - 1 else (52, 62, 78)
        if i == page - 1:
            d.rounded_rectangle([cx - 26, y + 30, cx, y + 36], radius=3, fill=c)
            cx -= 36
        else:
            d.ellipse([cx - 8, y + 28, cx, y + 36], fill=c)
            cx -= 18
    d.text((W - M - 200, y + 48), str(page) + " / " + str(total), font=fnt(18, 500), fill=(80, 90, 104))


def tip_banner(d, y, text, accent=MINT):
    tf = fnt(23, 400)
    lines = wrap(d, text, tf, W - 2 * M - 200)
    h = 92 + (len(lines) - 1) * 32
    d.rounded_rectangle([M, y, W - M, y + h], radius=18, fill=(18, 24, 20), outline=(52, 66, 40), width=2)
    d.rectangle([M + 1, y + 18, M + 5, y + h - 18], fill=accent)
    d.ellipse([M + 28, y + 26, M + 38, y + 36], fill=accent)
    tracked(d, M + 48, y + 21, "ПОДСКАЗКА", fnt(17, 700), accent, 2.4)
    yy = y + 52
    for ln in lines:
        d.text((M + 28, yy), ln, font=tf, fill=(206, 216, 228))
        yy += 32
    return y + h


def sheet(num, total, badge, title, subtitle, sections, name, accent=MINT, note=None):
    global img_global
    # измерение
    probe = Image.new("RGB", (W, 10))
    pd = ImageDraw.Draw(probe)
    h = 64 + 76 + 82 + 52 + 44 + 0 + 44  # header
    for sname, color, entries in sections:
        h += 62
        for cmd, desc in entries:
            rh, _ = measure_row(pd, cmd, desc)
            h += rh + 22
    if note:
        h += 110 + (len(wrap(pd, note, fnt(23, 400), W - 2 * M - 200)) - 1) * 32
    h += 70 + 40
    h = max(h, 900)
    img = background(W, h)
    img_global = img
    d = ImageDraw.Draw(img)
    y = header(d, badge, title, subtitle, accent)
    for i, (sname, color, entries) in enumerate(sections, start=1):
        y = section(d, y, "%02d" % i, sname, color)
        for cmd, desc in entries:
            y = row(d, y, cmd, desc, color)
        y += 16
    if note:
        y = tip_banner(d, y, note, accent) + 16
    footer(W, h, num, total, accent)
    p = os.path.join(OUT, name)
    img.save(p, quality=94, subsampling=1)
    return p


# ---------------- hero ----------------
def hero(name):
    h = 900
    img = background(W, h)
    global img_global
    img_global = img
    d = ImageDraw.Draw(img)

    y = 64
    bw = tracked_w("АДМИН-СИСТЕМА", fnt(19, 700), 2.6) + 44
    d.rounded_rectangle([M, y, M + bw, y + 44], radius=22, outline=(46, 66, 40), width=2, fill=(18, 26, 18))
    d.ellipse([M + 16, y + 17, M + 26, y + 27], fill=MINT)
    tracked(d, M + 36, y + 12, "АДМИН-СИСТЕМА", fnt(19, 700), MINT, 2.6)

    d.text((M - 3, 168), "Бот под", font=fnt(76, 800), fill=INK)
    d.text((M - 3, 256), "полным", font=fnt(76, 800), fill=MINT)
    d.text((M - 3, 344), "контролем", font=fnt(76, 800), fill=INK)
    d.text((M, 452), "Заявки, клиенты, отзывы, цены и статистика —\nв боте и на мини-сайте в реальном времени.",
           font=fnt(25, 400), fill=DIM, spacing=12)

    feats = [
        ("Панель в реальном времени", "слева от поля ввода, только у админов"),
        ("Ответ клиенту в 1 нажатие", "с шаблонами и статусами заявки"),
        ("Все изменения — с фото", "уведомление приходит обоим админам"),
    ]
    yy = 558
    for t, s in feats:
        d.ellipse([M, yy + 9, M + 10, yy + 19], fill=MINT)
        d.text((M + 26, yy), t, font=fnt(25, 700), fill=INK)
        d.text((M + 26, yy + 34), s, font=fnt(21, 400), fill=(120, 132, 150))
        yy += 92

    # ---------- телефон ----------
    px, py, pw, ph = 715, 120, 330, 660
    d.rounded_rectangle([px - 10, py - 10, px + pw + 10, py + ph + 10], radius=52, fill=(26, 33, 44))
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=44, fill=(14, 18, 25), outline=(44, 55, 70), width=2)
    # шапка чата
    d.rounded_rectangle([px + 2, py + 2, px + pw - 2, py + 96], radius=42, fill=(22, 29, 40))
    d.rectangle([px + 2, py + 60, px + pw - 2, py + 96], fill=(22, 29, 40))
    d.ellipse([px + 20, py + 34, px + 62, py + 76], fill=(38, 48, 62), outline=MINT, width=2)
    d.text((px + 34, py + 46), "СБ", font=fnt(18, 800), fill=MINT)
    d.text((px + 76, py + 36), "Сайты и боты", font=fnt(20, 700), fill=INK)
    d.text((px + 76, py + 62), "бот · онлайн", font=fnt(16, 400), fill=GREEN)
    # пузыри
    d.rounded_rectangle([px + 20, py + 120, px + 250, py + 196], radius=16, fill=(28, 36, 48))
    d.text((px + 38, py + 138), "Привет! Сделаю сайт", font=fnt(17, 400), fill=(226, 232, 240))
    d.text((px + 38, py + 162), "или бота за 2 дня.", font=fnt(17, 400), fill=(226, 232, 240))
    d.rounded_rectangle([px + 84, py + 214, px + 310, py + 262], radius=16, fill=(38, 52, 30))
    d.text((px + 102, py + 230), "Принял заявку #12", font=fnt(17, 600), fill=(214, 244, 170))
    # кнопки меню
    btn_y = py + 292
    for label, col in [("Каталог", (30, 38, 50)), ("Примеры", (30, 38, 50)),
                       ("Отзывы / FAQ", (30, 38, 50)), ("Связаться", (30, 38, 50))]:
        d.rounded_rectangle([px + 20, btn_y, px + pw - 20, btn_y + 58], radius=16, fill=col, outline=(48, 60, 76), width=2)
        d.text((px + 40, btn_y + 16), label, font=fnt(20, 600), fill=(206, 214, 226))
        btn_y += 70

    # строка ввода + кнопка «Панель» слева (только у админов)
    iy = py + ph - 82
    d.rounded_rectangle([px + 20, iy, px + 124, iy + 54], radius=14, fill=(34, 48, 24), outline=(90, 130, 40), width=2)
    d.text((px + 38, iy + 15), "Панель", font=fnt(19, 700), fill=MINT)
    d.rounded_rectangle([px + 136, iy, px + pw - 20, iy + 54], radius=14, fill=(26, 33, 44), outline=(44, 55, 70), width=2)
    d.text((px + 154, iy + 16), "Сообщение", font=fnt(18, 400), fill=(110, 122, 140))

    # ---------- окно панели ----------
    bx, by, bwd, bht = 960, 300, 380, 400
    d.rounded_rectangle([bx - 26, by - 26, bx + bwd + 26, by + bht + 34], radius=30, fill=(6, 8, 11))
    d.rounded_rectangle([bx, by, bx + bwd, by + bht], radius=18, fill=(13, 17, 24), outline=(46, 58, 74), width=2)
    d.rounded_rectangle([bx, by, bx + bwd, by + 54], radius=18, fill=(21, 27, 37))
    d.rectangle([bx, by + 34, bx + bwd, by + 54], fill=(21, 27, 37))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([bx + 16 + i * 20, by + 20, bx + 28 + i * 20, by + 32], fill=c)
    d.rounded_rectangle([bx + 84, by + 13, bx + bwd - 20, by + 41], radius=9, fill=(30, 38, 50))
    d.text((bx + 96, by + 19), "portfolio-bot.onrender.com/panel", font=fnt(15, 400), fill=(150, 162, 180))

    d.text((bx + 26, by + 76), "Панель бота", font=fnt(24, 700), fill=INK)
    d.text((bx + 26, by + 108), "обновление каждые 5 секунд", font=fnt(15, 400), fill=(120, 132, 150))
    cards = [("Запуски", "1 284", MINT), ("Обращения", "37", CYAN),
             ("Пользователи", "512", AMBER), ("Заявки", "12", GREEN)]
    cw2, chh = 156, 96
    for i, (k, v, c) in enumerate(cards):
        cx = bx + 26 + (i % 2) * (cw2 + 14)
        cy = by + 150 + (i // 2) * (chh + 14)
        d.rounded_rectangle([cx, cy, cx + cw2, cy + chh], radius=14, fill=(22, 29, 40), outline=(40, 50, 64), width=2)
        d.text((cx + 16, cy + 14), k, font=fnt(15, 400), fill=(126, 138, 156))
        d.text((cx + 16, cy + 40), v, font=fnt(32, 800), fill=c)
    d.ellipse([bx + 26, by + bht - 44, bx + 36, by + bht - 34], fill=GREEN)
    d.text((bx + 44, by + bht - 50), "live", font=fnt(16, 700), fill=GREEN)

    footer(W, h, 1, 5)
    p = os.path.join(OUT, name)
    img.save(p, quality=94, subsampling=1)
    return p


if __name__ == "__main__":
    paths = [hero("v2_0_hero.jpg")]

    paths.append(sheet(2, 5, "ТОЛЬКО ДЛЯ АДМИНОВ", "Основное и заявки", "С чего начать и как вести заказы", [
        ("Основное", MINT, [
            ("/admin  /settings", "Админ-меню: панель, цены, контакт, слоты, статистика"),
            ("/panel", "Личная ссылка на мини-сайт с данными бота в реальном времени"),
            ("/help_admin", "Полный список всех команд с описанием"),
            ("/ping", "Проверка: бот жив, время, тип хранилища"),
            ("/healthcheck", "Диагностика: время, хранилище, счётчики"),

            ("/db", "Postgres или файлы, задан ли DATABASE_URL"),
            ("/id", "Ваш chat_id — нужен для /say, /who, /note"),
        ]),
        ("Заявки", CYAN, [
            ("/tickets", "Последние 15 заявок: статус, клиент, суть"),
            ("/ticket ID", "Карточка + кнопки «Ответить» и статусы заказа"),
            ("/open_tickets", "Только открытые: новый, принят, в работе"),
            ("/done_tickets", "Только выполненные заявки"),
            ("/findticket текст", "Поиск по всем полям: имя, текст, статус"),
            ("/ticketmsg ID", "Только текст заявки, чтобы скопировать"),
            ("/setstatus ID статус", "Сменить статус — клиенту уйдёт уведомление. /setstatus 12 готово"),
        ]),
    ], "v2_1_osnovnoe.jpg",
        note="На любое обращение клиента приходит кнопка «Ответить» — ответ уходит прямо в бот клиенту."))

    paths.append(sheet(3, 5, "ТОЛЬКО ДЛЯ АДМИНОВ", "Клиенты, отзывы, рассылки", "Личные заметки, модерация и аудитория", [
        ("Клиенты и заметки", AMBER, [
            ("/who CHAT_ID", "Профиль: имя, сегмент, заметка, число заявок"),
            ("/note ID текст", "Заметка по клиенту (по заявке или chat_id)"),
            ("/notes ID", "Показать сохранённую заметку"),
            ("/delnote ID", "Удалить заметку"),
            ("/say CHAT_ID текст", "Сообщение клиенту от имени бота"),
            ("/clearstate CHAT_ID", "Сбросить «застрявшее» состояние диалога"),
            ("/lastusers N", "Последние N пользователей (макс. 50)"),
        ]),
        ("Отзывы", GREEN, [
            ("/reviews", "Последние отзывы и их статусы"),
            ("/reviews_pending", "На модерации, с кнопками «Опубликовать» / «Отклонить»"),
        ]),
        ("Аудитория и рассылки", CYAN, [
            ("/users", "Всего пользователей и последние"),
            ("/segments", "Сколько людей в каждом сегменте"),
            ("/rassylka", "Рассылка всем: фото, текст, кнопки"),
            ("/rassylka bots|sites", "Только выбранному сегменту (ещё catalog, brief)"),
            ("/broadcast_preview", "Как выглядит текст рассылки до отправки"),
        ]),
    ], "v2_2_klienty.jpg",
        note="/rassylka спрашивает текст и картинку: можно отправить фото и кнопки. Сегмент считается сам, когда клиент смотрит ботов, сайты или оформляет заявку."))

    paths.append(sheet(4, 5, "ТОЛЬКО ДЛЯ АДМИНОВ", "Статистика и настройки", "Цифры, цены, тексты и статусы бота", [
        ("Статистика и данные", MINT, [
            ("/stats", "Запуски, сообщения, обращения, заявки, отзывы"),
            ("/export", "Экспорт настроек в JSON"),
            ("/exportdata", "Сводка по заявкам, отзывам и сегментам"),
            ("/backup", "Настройки и сводка данных одним заходом"),
        ]),
        ("Настройки и контент", AMBER, [
            ("/prices", "Все услуги, цены и сроки"),
            ("/service ID", "Данные услуги: zayavki, zapis, site, menu, ai"),
            ("/setprice_svc ID цена", "Быстро сменить цену услуги"),
            ("/setslot текст", "Статус: «Принимаю заказы» или «Занят до…»"),
            ("/maintenance on|off", "Слот одним словом"),
            ("/setowner username", "Контакт для связи, без @"),
            ("/setfaq текст", "Заменить FAQ"),
            ("/setabout текст", "Заменить описание бота"),
            ("/faq", "Показать текущий статус и FAQ"),
        ]),
    ], "v2_3_nastroyki.jpg",
        note="Цену пишите как удобно: «750» или «750 ₽». После изменения всем админам придёт фото с тем, что было и что стало."))

    paths.append(sheet(5, 5, "ТОЛЬКО ДЛЯ АДМИНОВ", "Служебное и шпаргалка", "Мелочи, которые экономят время", [
        ("Служебное", CYAN, [
            ("/links", "Deep-link ссылки на каждую услугу — для постов"),
            ("/notifyadmins текст", "Сообщение всем администраторам"),
            ("/version", "Версия бота и тип хранилища"),
            ("/chatinfo", "chat_id, признак админа, username"),
        ]),
        ("Шпаргалка", GREEN, [
            ("статусы", "новый → принят → в работе → готово"),
            ("сегменты", "bots · sites · catalog · brief"),
            ("услуги", "zayavki · zapis · site · menu · ai"),
            ("правило", "любое изменение настроек приходит обоим админам с фото"),
        ]),
    ], "v2_4_service.jpg",
        note="Полный список команд всегда под рукой: /help_admin. Меню «/» в чате с ботом у админов тоже показывает команды."))

    for p in paths:
        print(p, os.path.getsize(p))
