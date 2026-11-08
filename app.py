import os
import re
import json
import time
import threading
import requests
from urllib.parse import quote
from flask import Flask, request, jsonify

# ---------- настройки ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
_ADMIN_RAW = os.environ.get("ADMIN_ID", "")
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "")  # без @
POLLING = os.environ.get("POLLING", "") == "1"
PREMIUM = os.environ.get("PREMIUM", "0") == "1"

ADMIN_IDS = set(x.strip() for x in _ADMIN_RAW.replace(";", ",").split(",") if x.strip())
# создатели
for _aid in ("8009841546", "8363676077"):
    if _aid:
        ADMIN_IDS.add(_aid)


def is_admin(chat_id):
    return str(chat_id) in ADMIN_IDS

HERE = os.path.dirname(os.path.abspath(__file__))
EMOJI_FILE = os.path.join(HERE, "emoji_ids.json")
BASE = "https://api.telegram.org/bot" + BOT_TOKEN

app = Flask(__name__)
state = {}
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")
USERS_FILE = os.path.join(HERE, "users.json")


def load_users():
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(u):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("users save error:", e)


USERS = load_users()


def remember(chat_id, user):
    key = str(chat_id)
    name = user.get("username") or user.get("first_name") or "-"
    if USERS.get(key) != name:
        USERS[key] = name
        save_users(USERS)


# ---------- настройки бота (базовые, меняются админами) ----------
SETTINGS_FILE = os.path.join(HERE, "settings.json")

DEFAULT_SETTINGS = {
    "owner_username": OWNER_USERNAME or "z0nchik",
    "services": {
        "zayavki": {"title": "Бот приёма заявок", "price": "750 ₽", "term": "1–2 дня", "desc": "Клиент пишет боту — заявка сразу падает вам в личку. Меню, кнопки, уведомления."},
        "zapis": {"title": "Бот записи", "price": "1 250 ₽", "term": "2–3 дня", "desc": "Услуга → мастер → время. Напоминание за час. Клиенты записываются сами."},
        "site": {"title": "Сайт-визитка", "price": "500 ₽", "term": "2–4 дня", "desc": "Услуги, цены, фото, форма заявки. Открывается с телефона, заявки приходят в телеграм."},
        "menu": {"title": "Меню по QR", "price": "750 ₽", "term": "1–2 дня", "desc": "Для кафе и доставки: гость сканирует QR, видит меню и делает заказ без звонка."},
        "ai": {"title": "ИИ-бот по документам", "price": "2 000 ₽", "term": "3–5 дней", "desc": "Отвечает клиентам по вашему прайсу и документам. Без вашего участия, 24/7."},
    },
    "about": "Делаю сайты и телеграм-ботов под конкретную задачу: приём заявок, запись клиентов, меню по QR, ответы на вопросы, автоматизация мелочей.\n\nДля бизнеса, учёбы и личных проектов — от простой визитки до бота, который работает вместо администратора.\n\nЦена и срок известны заранее. Демо показываю до оплаты. Если задача не моя — скажу прямо.",
}


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # merge defaults
        out = json.loads(json.dumps(DEFAULT_SETTINGS))
        if isinstance(data, dict):
            if data.get("owner_username"): out["owner_username"] = data["owner_username"]
            if data.get("about"): out["about"] = data["about"]
            sv = data.get("services") or {}
            if isinstance(sv, dict):
                for k, v in sv.items():
                    if k in out["services"] and isinstance(v, dict):
                        out["services"][k].update({kk: vv for kk, vv in v.items() if vv})
        return out
    except Exception:
        return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(cfg):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("settings save error:", e)


SETTINGS = load_settings()


def owner_username():
    return (SETTINGS.get("owner_username") or OWNER_USERNAME or "z0nchik").lstrip("@")


def _make_change_photo(title, details):
    try:
        from PIL import Image, ImageDraw, ImageFont
        FONT = "/tmp/Onest.ttf"
        W, H = 1280, 720
        def fnt(size, weight=700):
            f = ImageFont.truetype(FONT, size)
            try: f.set_variation_by_axes([weight])
            except Exception: pass
            return f
        # bg
        img = Image.new("RGB", (W, H), (11, 14, 19))
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y/(H-1)
            c = tuple(int(11 + (20-11)*t) if i<2 else int(19 + (34-19)*t) for i in range(3))
            d.line([(0,y),(W,y)], fill=c)
        for x in range(0,W,60): d.line([(x,0),(x,H)], fill=(24,30,38), width=1)
        for y in range(0,H,60): d.line([(0,y),(W,y)], fill=(24,30,38), width=1)
        acc = (182,255,62)
        d.text((72,60), "ИЗМЕНЕНИЕ В БОТЕ", font=fnt(26,600), fill=acc)
        d.rectangle([72,98,260,102], fill=acc)
        # wrap title
        d.text((68,170), title[:60], font=fnt(52,800), fill=(246,248,250))
        y = 270
        for line in (details or "").split("\n"):
            line = line.strip()
            if not line: y += 14; continue
            # wrap
            words, cur = line.split(), ""
            for w in words:
                test = (cur+" "+w).strip()
                if d.textbbox((0,0), test, font=fnt(26,400))[2] < 1120: cur = test
                else:
                    d.text((72,y), cur, font=fnt(26,400), fill=(138,148,166)); y += 38; cur = w
            if cur:
                d.text((72,y), cur, font=fnt(26,400), fill=(138,148,166)); y += 38
            if y > 620: break
        d.rounded_rectangle([72, H-110, 520, H-54], radius=28, fill=(28,36,46), outline=acc, width=2)
        d.text((104, H-96), "уведомление администраторов", font=fnt(22,600), fill=acc)
        path = os.path.join(HERE, "change_notice.jpg")
        img.save(path, quality=92)
        return path
    except Exception as e:
        print("change photo error:", e)
        return ""


def notify_change(who_name, title, details):
    caption = "<b>%s</b>\n\n%s\n\nИзменил: %s" % (title, details, who_name)
    photo = _make_change_photo(title, details)
    for aid in ADMIN_IDS:
        if photo:
            send_photo_file(aid, caption, None, os.path.basename(photo))
        else:
            send(aid, caption)


def _asset(name):
    for p in (os.path.join(HERE, "assets", name), os.path.join(HERE, name)):
        if os.path.exists(p):
            return p
    return ""


try:
    with open(EMOJI_FILE, encoding="utf-8") as f:
        EMOJI_IDS = json.load(f)
except Exception:
    EMOJI_IDS = {}

TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.+?)</tg-emoji>', re.S)


def premium(text):
    if not PREMIUM or not EMOJI_IDS:
        return text
    for emoji, eid in EMOJI_IDS.items():
        if emoji in text:
            text = text.replace(emoji, '<tg-emoji emoji-id="%s">%s</tg-emoji>' % (eid, emoji))
    return text


def plain(text):
    return TG_EMOJI_RE.sub(r"\1", text)


# ---------- каталог ----------
_SERVICE_META = {
    "zayavki": {"photo": "svc_zayavki.jpg"},
    "zapis": {"photo": "svc_zapis.jpg"},
    "site": {"photo": "svc_site.jpg"},
    "menu": {"photo": "svc_menu.jpg"},
    "ai": {"photo": "svc_ai.jpg"},
}
_SERVICE_ORDER = ["zayavki", "zapis", "site", "menu", "ai"]

CUSTOM = {
    "id": "custom",
    "title": "Свой вариант",
    "price": "по задаче",
    "term": "обсудим",
    "photo": "svc_custom.jpg",
    "desc": "Не нашли нужное? Опишите задачу — скажу, возьмусь или нет, и сколько это стоит.",
}


def get_services():
    sv = SETTINGS.get("services") or {}
    out = []
    for sid in _SERVICE_ORDER:
        d = dict((DEFAULT_SETTINGS["services"].get(sid) or {}))
        d.update(sv.get(sid) or {})
        d["id"] = sid
        d["photo"] = _SERVICE_META.get(sid, {}).get("photo", "svc_custom.jpg")
        out.append(d)
    return out

SERVICES = get_services()


def svc(sid):
    for s in get_services():
        if s["id"] == sid:
            return s
    return CUSTOM


# ---------- Telegram API ----------
def api(method, **params):
    try:
        r = requests.post(BASE + "/" + method, json=params, timeout=25)
        return r.json()
    except Exception as e:
        print("API error:", e)
        return {}


def send(chat_id, text, keyboard=None, reply_keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": premium(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    elif reply_keyboard:
        payload["reply_markup"] = reply_keyboard
    res = api("sendMessage", **payload)
    if not res.get("ok"):
        payload["text"] = plain(payload["text"])
        res = api("sendMessage", **payload)
    return res


def send_animation(chat_id, caption, keyboard=None, filename=""):
    path = _asset(filename) if filename else _asset("intro.jpg")
    if not path:
        return send(chat_id, caption, keyboard)
    payload = {"chat_id": chat_id, "caption": premium(caption), "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        with open(path, "rb") as f:
            res = requests.post(
                BASE + "/sendAnimation",
                data=payload,
                files={"animation": (os.path.basename(path), f, "image/gif")},
                timeout=60,
            ).json()
    except Exception as e:
        print("Animation error:", e)
        return send(chat_id, caption, keyboard)
    if not res.get("ok"):
        print("Animation failed:", res.get("description"))
        if keyboard:
            payload.pop("reply_markup", None)
            try:
                with open(path, "rb") as f:
                    res2 = requests.post(
                        BASE + "/sendAnimation",
                        data=payload,
                        files={"animation": (os.path.basename(path), f, "image/gif")},
                        timeout=60,
                    ).json()
                if res2.get("ok"):
                    send(chat_id, "Выберите действие:", keyboard)
                    return res2
            except Exception as e:
                print("Animation retry error:", e)
        return send(chat_id, caption, keyboard)
    return res


def send_photo_file(chat_id, caption, keyboard=None, filename="", reply_keyboard=None):
    path = _asset(filename)
    if not path:
        return send(chat_id, caption, keyboard, reply_keyboard=reply_keyboard)
    payload = {"chat_id": chat_id, "caption": premium(caption), "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    elif reply_keyboard:
        payload["reply_markup"] = json.dumps(reply_keyboard)
    mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    try:
        with open(path, "rb") as f:
            res = requests.post(
                BASE + "/sendPhoto",
                data=payload,
                files={"photo": (os.path.basename(path), f, mime)},
                timeout=60,
            ).json()
    except Exception as e:
        print("Photo error:", e)
        return send(chat_id, caption, keyboard, reply_keyboard=reply_keyboard)
    if not res.get("ok"):
        print("Photo failed:", res.get("description"))
        return send(chat_id, caption, keyboard, reply_keyboard=reply_keyboard)
    return res


def send_video_file(chat_id, caption, keyboard=None, filename="", supports_streaming=True):
    path = _asset(filename)
    if not path:
        return send(chat_id, caption, keyboard)
    payload = {
        "chat_id": chat_id,
        "caption": premium(caption),
        "parse_mode": "HTML",
        "supports_streaming": "true" if supports_streaming else "false",
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        with open(path, "rb") as f:
            res = requests.post(
                BASE + "/sendVideo",
                data=payload,
                files={"video": (os.path.basename(path), f, "video/mp4")},
                timeout=120,
            ).json()
    except Exception as e:
        print("Video error:", e)
        return send(chat_id, caption, keyboard)
    if not res.get("ok"):
        print("Video failed:", res.get("description"))
        if keyboard:
            payload.pop("reply_markup", None)
            try:
                with open(path, "rb") as f:
                    res2 = requests.post(
                        BASE + "/sendVideo",
                        data=payload,
                        files={"video": (os.path.basename(path), f, "video/mp4")},
                        timeout=120,
                    ).json()
                if res2.get("ok"):
                    send(chat_id, "Выберите действие:", keyboard)
                    return res2
            except Exception as e:
                print("Video retry error:", e)
        return send(chat_id, caption, keyboard)
    return res


def answer_cb(cb_id):
    api("answerCallbackQuery", callback_query_id=cb_id)


def bot_username():
    global BOT_USERNAME
    if not BOT_USERNAME:
        me = api("getMe")
        BOT_USERNAME = me.get("result", {}).get("username", "")
    return BOT_USERNAME


def deep_link(sid):
    return "https://t.me/%s?start=order_%s" % (bot_username(), sid)


def dm_link(text):
    ou = owner_username()
    if not ou:
        return ""
    return "https://t.me/%s?text=%s" % (ou, quote(text))


# ---------- тексты ----------
HELLO = (
    "Привет.\n\n"
    "Я делаю <b>сайты и телеграм-ботов</b> под любую задачу: бизнес, учёба, личные проекты.\n\n"
    "Выберите, что нужно — покажу цену и срок."
)

ABOUT = (
    "О боте\n\n"
    "Делаю сайты и телеграм-ботов под конкретную задачу: приём заявок, запись клиентов, "
    "меню по QR, ответы на вопросы, автоматизация мелочей.\n\n"
    "Для бизнеса, учёбы и личных проектов — от простой визитки до бота, который работает "
    "вместо администратора.\n\n"
    "Цена и срок известны заранее. Демо показываю до оплаты. Если задача не моя — скажу прямо."
)

MENU = [
    [{"text": "Каталог услуг", "callback_data": "catalog", "style": "primary"}],
    [{"text": "Примеры работ", "callback_data": "examples"}],
    [{"text": "Как я работаю", "callback_data": "trust"}],
    [{"text": "Связаться", "callback_data": "contact"}],
]

REPLY_KB = {
    "keyboard": [
        [{"text": "Каталог"}, {"text": "Примеры"}],
        [{"text": "Как работаю"}, {"text": "Связаться"}],
        [{"text": "Свой вариант"}, {"text": "Меню"}],
    ],
    "resize_keyboard": True,
}

BACK = [[{"text": "В меню", "callback_data": "menu"}]]

EXAMPLES_ASK = (
    "<b>Примеры работ</b>\n\n"
    "Выберите раздел — покажу видео с 4 сценариями в каждом.\n\n"
    "Боты: запись, заявки, меню по QR, ответы по прайсу.\n"
    "Сайты: визитка, лендинг, портфолио, каталог."
)

EXAMPLES_KB = [
    [{"text": "Примеры ботов", "callback_data": "ex_bots"}],
    [{"text": "Примеры сайтов", "callback_data": "ex_sites"}],
    [{"text": "В меню", "callback_data": "menu"}],
]

EXAMPLES_BOTS_CAPTION = (
    "<b>Примеры ботов</b>\n\n"
    "1. <b>Бот записи</b> — для салона, мастера, студии. Клиент выбирает услугу, мастера и время. "
    "Вам приходит запись, клиенту — подтверждение.\n\n"
    "2. <b>Бот заявок</b> — для магазина, услуг, доставки. Человек выбирает нужное и оставляет контакты, "
    "заявка сразу падает вам в личку.\n\n"
    "3. <b>Меню по QR</b> — для кафе и точек выдачи. Гость сканирует код, смотрит меню и делает заказ без звонка.\n\n"
    "4. <b>ИИ-бот</b> — отвечает по вашему прайсу, документам или правилам. Работает круглосуточно, без вашего участия.\n\n"
    "Каждый бот собираю под вашу задачу: свои кнопки, тексты, логика и куда приходят заявки. "
    "Срок обычно 1–3 дня, цена — в каталоге."
)

EXAMPLES_SITES_CAPTION = (
    "<b>Примеры сайтов</b>\n\n"
    "1. <b>Сайт-визитка</b> — для мастера, специалиста, небольшого дела. Услуги, цены, фото, кнопка записи или связи.\n\n"
    "2. <b>Лендинг</b> — одна страница под одну задачу: ремонт, услуги, набор. Коротко объясняет и ведёт к заявке, заявка уходит вам в телеграм.\n\n"
    "3. <b>Портфолио</b> — для фотографа, дизайнера, исполнителя. Работы, описание, контакты, быстрый способ написать.\n\n"
    "4. <b>Каталог</b> — витрина товаров или позиций без сложной оплаты. Человек смотрит и оформляет заказ сообщением.\n\n"
    "Сайты делаю под телефон: быстро открываются, понятно читаются, заявки приходят вам в телеграм. "
    "Срок обычно 2–4 дня."
)

TRUST_CAPTION = (
    "<b>Как я работаю</b>\n\n"
    "1. <b>Обсуждаем задачу</b> — вы описываете, что нужно. Я говорю цену, срок и что именно будет сделано. Без сюрпризов по ходу работы.\n\n"
    "2. <b>Показываю демо</b> — сначала вы видите рабочий результат: как выглядит, какие кнопки, куда приходят заявки. Решение по оплате принимаете уже по делу.\n\n"
    "3. <b>Передаю всё</b> — после согласования отдаю доступ и исходники. Проект остаётся у вас, вы не зависите от меня.\n\n"
    "4. <b>На связи</b> — отвечаю в телеграме. Если что-то сломалось по моей части, помогаю разобраться.\n\n"
    "В боте есть 8 примеров (боты и сайты) — их можно открыть и посмотреть прямо сейчас в разделе «Примеры работ»."
)

CUSTOM_ASK = (
    "<b>Свой вариант</b>\n\n"
    "Опишите задачу одним сообщением: что нужно, для чего и какой срок.\n\n"
    "Я посмотрю и скажу честно — возьмусь или нет, и сколько будет стоить."
)

CUSTOM_DONE = (
    "Записал.\n\n"
    "Я прочитаю и отвечу. Если задача не моя — так и скажу, без воды."
)

BARGAIN_ASK = (
    "<b>Предложить свою цену</b>\n\n"
    "Можно обсудить цену. Напишите одним сообщением:\n"
    "— какая услуга или задача;\n"
    "— ваш бюджет или предложение.\n\n"
    "Посмотрю и отвечу честно — получится ли сделать за эту сумму."
)

BARGAIN_DONE = (
    "Предложение записал.\n\n"
    "Посмотрю задачу и бюджет, отвечу в личку."
)

ASK_PROMPT = (
    "<b>Сообщение в боте</b>\n\n"
    "Напишите ваш вопрос или детали одним сообщением — я получу его здесь и отвечу в этом чате."
)

ASK_DONE = (
    "Сообщение отправлено.\n\n"
    "Я отвечу здесь, в боте."
)


def catalog_text():
    lines = ["<b>Каталог услуг</b>\n"]
    for s in get_services():
        lines.append("• <b>%s</b> — %s" % (s["title"], s["price"]))
    lines.append("• <b>Свой вариант</b> — по задаче")
    lines.append("\nЦены можно обсудить — есть кнопка «Предложить свою цену».")
    lines.append("Нажмите на услугу, чтобы посмотреть описание.")
    return "\n".join(lines)


def catalog_kb():
    rows = []
    for s in get_services():
        rows.append([{"text": "%s · %s" % (s["title"], s["price"]), "callback_data": "svc:" + s["id"]}])
    rows.append([{"text": "Свой вариант", "callback_data": "svc:custom"}])
    rows.append([{"text": "Предложить свою цену", "callback_data": "bargain"}])
    rows.append([{"text": "В меню", "callback_data": "menu"}])
    return rows


def service_caption(s):
    return (
        "<b>%s</b>\n\n%s\n\n"
        "<b>%s</b> · срок %s\n\n"
        "Можно написать в личку или прямо здесь, в боте — я отвечу."
    ) % (s["title"], s["desc"], s["price"], s["term"])


def service_kb(s):
    rows = []
    if s["id"] == "custom":
        rows.append([{"text": "Описать задачу", "callback_data": "custom"}])
        draft = "Здравствуйте! Пишу из бота. У меня своя задача, хочу обсудить цену и срок."
    else:
        draft = "Здравствуйте! Пишу из бота. Интересует «%s» — %s. Хочу уточнить детали." % (
            s["title"], s["price"]
        )
    link = dm_link(draft)
    if link:
        rows.append([{"text": "Написать в личку", "url": link}])
    rows.append([{"text": "Написать в боте", "callback_data": "ask"}])
    rows.append([{"text": "Назад к каталогу", "callback_data": "catalog"}])
    return rows


def contact_text():
    ou = owner_username(); owner = ("@" + ou) if ou else "ответным сообщением"
    return "<b>Связаться</b>\n\nТелеграм: %s\n\nОтвечаю быстро — телефон под рукой." % owner


def contact_kb():
    rows = []
    link = dm_link("Здравствуйте! Пишу из бота. Хочу обсудить заказ.")
    if link:
        rows.append([{"text": "Написать в личку", "url": link}])
    rows.append([{"text": "Написать в боте", "callback_data": "ask"}])
    rows.append([{"text": "В меню", "callback_data": "menu"}])
    return rows


# ---------- отправка ----------
def show_menu(chat_id):
    send_photo_file(chat_id, HELLO, MENU, "intro.jpg", reply_keyboard=REPLY_KB)


def show_catalog(chat_id):
    send_photo_file(chat_id, catalog_text(), catalog_kb(), "scr_catalog.jpg")


def show_service(chat_id, sid):
    s = svc(sid)
    send_photo_file(chat_id, service_caption(s), service_kb(s), s.get("photo",""))


def reply_kb(chat_id):
    return [[{"text": "Ответить", "callback_data": "reply:%s" % chat_id}]]


def notify_admin(text, reply_to=None):
    kb = reply_kb(reply_to) if reply_to else None
    for aid in ADMIN_IDS:
        send(aid, text, keyboard=kb)


def handle_buy(chat_id, user, sid):
    item = svc(sid)
    notify_admin(
        "<b>ЗАКАЗ / ИНТЕРЕС</b>\n\n"
        "Услуга: <b>%s</b> (%s)\n"
        "Клиент: %s (@%s)\n"
        "<code>%s</code>"
        % (item["title"], item["price"], user.get("first_name", "-"), user.get("username", "-"), chat_id),
        reply_to=chat_id,
    )
    rows = []
    link = dm_link(
        "Здравствуйте! Пишу из бота. Интересует «%s» — %s. Хочу уточнить детали."
        % (item["title"], item["price"])
    )
    if link:
        rows.append([{"text": "Написать в личку", "url": link}])
    rows.append([{"text": "Написать в боте", "callback_data": "ask"}])
    rows.append([{"text": "В меню", "callback_data": "menu"}])
    send(
        chat_id,
        "По услуге <b>%s</b> можно написать мне в личку или прямо здесь, в боте — я отвечу."
        % item["title"],
        rows,
    )


# ---------- рассылка ----------
BROADCAST_TEXT = (
    "<b>Примеры и условия</b>\n\n"
    "Собираю телеграм-ботов и сайты под задачу. "
    "В видео — 8 примеров и как устроена работа: сначала показываю результат, потом решаете по оплате.\n\n"
    "Выберите, что посмотреть."
)


def broadcast_kb():
    rows = [
        [{"text": "Примеры ботов", "callback_data": "ex_bots"}],
        [{"text": "Примеры сайтов", "callback_data": "ex_sites"}],
        [{"text": "Каталог с ценами", "callback_data": "catalog"}],
    ]
    link = dm_link("Здравствуйте! Пишу из бота. Хочу обсудить задачу.")
    if link:
        rows.append([{"text": "Написать в личку", "url": link}])
    return rows


def broadcast():
    ok = fail = 0
    kb = broadcast_kb()
    for cid in list(USERS.keys()):
        r = send_photo_file(cid, BROADCAST_TEXT, kb, "trust.jpg")
        if r.get("ok"):
            ok += 1
        else:
            fail += 1
            print("broadcast fail:", cid, r.get("description"))
        time.sleep(1.0)
    return ok, fail



# ---------- настройки (админ) ----------
def show_settings(chat_id):
    ou = owner_username()
    rows = [
        [{"text": "Цены услуг", "callback_data": "adm:prices"}],
        [{"text": "Контакт (@" + (ou or "-") + ")", "callback_data": "adm:owner"}],
        [{"text": "В меню", "callback_data": "menu"}],
    ]
    send(chat_id, "<b>Настройки бота</b>\n\nБазовые настройки. Каждое изменение придёт всем администраторам с уведомлением.", keyboard=rows)


def show_price_settings(chat_id):
    rows = []
    for sv in get_services():
        rows.append([{"text": "%s — %s" % (sv["title"], sv["price"]), "callback_data": "adm:setp:%s" % sv["id"]}])
    rows.append([{"text": "Назад", "callback_data": "adm:back"}])
    send(chat_id, "<b>Цены услуг</b>\n\nНажмите на услугу, чтобы изменить цену.", keyboard=rows)

# ---------- обработка ----------
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    user = msg.get("from", {})

    try:
        with open("/tmp/chatids.log", "a") as f:
            f.write("%s %s\n" % (chat_id, user.get("username", "-")))
    except Exception:
        pass
    remember(chat_id, user)

    # ответ админа пользователю (внутри бота)
    if is_admin(chat_id):
        st = state.get(chat_id, {})
        if st.get("step") == "reply" and text and not text.startswith("/"):
            if text.lower() in ("отмена", "cancel", "меню"):
                state.pop(chat_id, None)
                return send(chat_id, "Ответ отменён.", [[{"text": "В меню", "callback_data": "menu"}]])
            to = st.get("to")
            state.pop(chat_id, None)
            if to:
                send(
                    to,
                    "<b>Ответ от продавца</b>\n\n%s" % text,
                    keyboard=[[{"text": "Ответить в боте", "callback_data": "ask"}]],
                )
                return send(chat_id, "Ответ отправлен пользователю <code>%s</code>." % to)
            return send(chat_id, "Не найден получатель.", [[{"text": "В меню", "callback_data": "menu"}]])
        if st.get("step", "").startswith("setprice:") and text and not text.startswith("/"):
            if text.lower() in ("отмена", "cancel"):
                state.pop(chat_id, None)
                return show_price_settings(chat_id)
            sid = st["step"].split(":", 1)[1]
            old = (SETTINGS.get("services", {}).get(sid) or {}).get("price") or (DEFAULT_SETTINGS["services"].get(sid) or {}).get("price") or "-"
            SETTINGS.setdefault("services", {}).setdefault(sid, {})["price"] = text
            save_settings(SETTINGS)
            global SERVICES
            SERVICES = get_services()
            state.pop(chat_id, None)
            who = user.get("username") or user.get("first_name") or str(chat_id)
            sv = svc(sid)
            notify_change(who, "Цена изменена", "Услуга: %s\nБыло: %s\nСтало: %s" % (sv["title"], old, text))
            return show_price_settings(chat_id)
        if st.get("step") == "setowner" and text and not text.startswith("/"):
            if text.lower() in ("отмена", "cancel"):
                state.pop(chat_id, None)
                return show_settings(chat_id)
            old = owner_username()
            SETTINGS["owner_username"] = text.lstrip("@").strip()
            save_settings(SETTINGS)
            state.pop(chat_id, None)
            who = user.get("username") or user.get("first_name") or str(chat_id)
            notify_change(who, "Контакт изменён", "Было: @%s\nСтало: @%s" % (old, owner_username()))
            return show_settings(chat_id)

    if text.startswith("/start"):
        state.pop(chat_id, None)
        payload = text[6:].strip()
        if payload.startswith("order_"):
            return show_service(chat_id, payload[6:])
        return show_menu(chat_id)

    if text == "/id":
        return send(chat_id, "Ваш chat_id: <code>%s</code>" % chat_id)

    if text == "/about":
        return send(chat_id, ABOUT, [[{"text": "Каталог услуг", "callback_data": "catalog"}]])

    if text in ("/catalog", "/menu"):
        return show_catalog(chat_id) if text == "/catalog" else show_menu(chat_id)
    if text == "/examples":
        return send_photo_file(chat_id, EXAMPLES_ASK, EXAMPLES_KB, "scr_examples.jpg")
    if text == "/trust":
        rows = [[{"text": "Примеры работ", "callback_data": "examples"}],[{"text": "Каталог с ценами", "callback_data": "catalog"}],[{"text": "В меню", "callback_data": "menu"}]]
        return send_photo_file(chat_id, TRUST_CAPTION, rows, "trust.jpg")
    if text == "/contact":
        return send_photo_file(chat_id, contact_text(), contact_kb(), "scr_contact.jpg")

    if text == "/links" and is_admin(chat_id):
        rows = ["<b>Ссылки для постов</b>\n", "Кидай в ВК или куда угодно — человек попадёт сразу на услугу:\n"]
        for s in get_services():
            rows.append("<b>%s</b>\n%s\n" % (s["title"], deep_link(s["id"])))
        rows.append("<b>Свой вариант</b>\n%s" % deep_link("custom"))
        return send(chat_id, "\n".join(rows))

    if text.startswith("/rassylka") and is_admin(chat_id):
        ok, fail = broadcast()
        return send(chat_id, "Разослано: %s. Не дошло: %s. Всего в базе: %s." % (ok, fail, len(USERS)))

    if text == "/settings" and is_admin(chat_id):
        return show_settings(chat_id)

    # быстрые кнопки снизу (reply keyboard)
    quick = {
        "каталог": "catalog",
        "примеры": "examples",
        "примеры работ": "examples",
        "как работаю": "trust",
        "как я работаю": "trust",
        "связаться": "contact",
        "свой вариант": "custom",
        "меню": "menu",
    }
    q = quick.get(text.lower())

    def _route(qk):
        if qk == "menu":
            return show_menu(chat_id)
        if qk == "catalog":
            return show_catalog(chat_id)
        if qk == "examples":
            return send_photo_file(chat_id, EXAMPLES_ASK, EXAMPLES_KB, "scr_examples.jpg")
        if qk == "trust":
            rows = [
                [{"text": "Примеры работ", "callback_data": "examples"}],
                [{"text": "Каталог с ценами", "callback_data": "catalog"}],
                [{"text": "В меню", "callback_data": "menu"}],
            ]
            return send_photo_file(chat_id, TRUST_CAPTION, rows, "trust.jpg")
        if qk == "contact":
            return send_photo_file(chat_id, contact_text(), contact_kb(), "scr_contact.jpg")
        return None

    step = state.get(chat_id, {}).get("step")
    if step == "custom":
        if q and q != "custom":
            state.pop(chat_id, None)
            r = _route(q)
            if r is not None:
                return r
        state.pop(chat_id, None)
        notify_admin(
            "<b>СВОЙ ВАРИАНТ</b>\n\n"
            "%s (@%s)\n"
            "<code>%s</code>\n\n"
            "%s"
            % (user.get("first_name", "-"), user.get("username", "-"), chat_id, text),
            reply_to=chat_id,
        )
        return send(chat_id, CUSTOM_DONE, [[{"text": "В меню", "callback_data": "menu"}]])

    if step == "bargain":
        if q and q not in ("custom",):
            state.pop(chat_id, None)
            r = _route(q)
            if r is not None:
                return r
        state.pop(chat_id, None)
        notify_admin(
            "<b>ПРЕДЛОЖЕНИЕ ЦЕНЫ</b>\n\n"
            "%s (@%s)\n"
            "<code>%s</code>\n\n"
            "%s"
            % (user.get("first_name", "-"), user.get("username", "-"), chat_id, text),
            reply_to=chat_id,
        )
        return send(chat_id, BARGAIN_DONE, [[{"text": "В меню", "callback_data": "menu"}]])

    if step == "ask":
        if q:
            state.pop(chat_id, None)
            r = _route(q)
            if r is not None:
                return r
        state.pop(chat_id, None)
        notify_admin(
            "<b>СООБЩЕНИЕ В БОТЕ</b>\n\n"
            "%s (@%s)\n"
            "<code>%s</code>\n\n"
            "%s"
            % (user.get("first_name", "-"), user.get("username", "-"), chat_id, text),
            reply_to=chat_id,
        )
        return send(chat_id, ASK_DONE, [[{"text": "В меню", "callback_data": "menu"}]])

    r = _route(q)
    if r is not None:
        return r
    if q == "custom":
        state[chat_id] = {"step": "custom"}
        return send_photo_file(chat_id, CUSTOM_ASK, [[{"text": "В меню", "callback_data": "menu"}]], "scr_custom.jpg")

    send(chat_id, "Выберите пункт в меню.", MENU, reply_keyboard=REPLY_KB)


def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    user = cb.get("from", {})
    data = cb.get("data", "")
    answer_cb(cb["id"])

    if data == "menu":
        state.pop(chat_id, None)
        return show_menu(chat_id)
    if data == "catalog":
        return show_catalog(chat_id)
    if data == "examples":
        return send_photo_file(chat_id, EXAMPLES_ASK, EXAMPLES_KB, "scr_examples.jpg")
    if data == "ex_bots":
        return send_photo_file(
            chat_id, EXAMPLES_BOTS_CAPTION,
            [[{"text": "Примеры сайтов", "callback_data": "ex_sites"}], [{"text": "В меню", "callback_data": "menu"}]],
            "examples_bots.jpg",
        )
    if data == "ex_sites":
        return send_photo_file(
            chat_id, EXAMPLES_SITES_CAPTION,
            [[{"text": "Примеры ботов", "callback_data": "ex_bots"}], [{"text": "В меню", "callback_data": "menu"}]],
            "examples_sites.jpg",
        )
    if data == "trust":
        rows = [
            [{"text": "Примеры работ", "callback_data": "examples"}],
            [{"text": "Каталог с ценами", "callback_data": "catalog"}],
            [{"text": "В меню", "callback_data": "menu"}],
        ]
        return send_photo_file(chat_id, TRUST_CAPTION, rows, "trust.jpg")
    if data == "contact":
        return send_photo_file(chat_id, contact_text(), contact_kb(), "scr_contact.jpg")
    if data == "custom":
        state[chat_id] = {"step": "custom"}
        return send_photo_file(chat_id, CUSTOM_ASK, [[{"text": "В меню", "callback_data": "menu"}]], "scr_custom.jpg")
    if data == "bargain":
        state[chat_id] = {"step": "bargain"}
        return send_photo_file(chat_id, BARGAIN_ASK, [[{"text": "В меню", "callback_data": "menu"}]], "scr_catalog.jpg")
    if data == "ask":
        state[chat_id] = {"step": "ask"}
        return send(chat_id, ASK_PROMPT, [[{"text": "В меню", "callback_data": "menu"}]])
    if data.startswith("reply:"):
        if not is_admin(chat_id):
            return send(chat_id, "Недоступно.")
        to = data.split(":", 1)[1].strip()
        state[chat_id] = {"step": "reply", "to": to}
        return send(chat_id, "Введите ответ для <code>%s</code>. Напишите «отмена», чтобы выйти." % to,
                    [[{"text": "Отмена", "callback_data": "cancelreply"}]])
    if data == "cancelreply" and is_admin(chat_id):
        state.pop(chat_id, None)
        return send(chat_id, "Ответ отменён.", [[{"text": "В меню", "callback_data": "menu"}]])
    if data == "adm:back" and is_admin(chat_id):
        return show_settings(chat_id)
    if data == "adm:prices" and is_admin(chat_id):
        return show_price_settings(chat_id)
    if data == "adm:owner" and is_admin(chat_id):
        state[chat_id] = {"step": "setowner"}
        return send(chat_id, "Текущий контакт: @%s\n\nОтправьте новый username (без @) или «отмена»." % owner_username())
    if data.startswith("adm:setp:") and is_admin(chat_id):
        sid = data.split(":", 2)[2]
        sv = svc(sid)
        state[chat_id] = {"step": "setprice:%s" % sid}
        return send(chat_id, "Услуга: <b>%s</b>\nТекущая цена: <b>%s</b>\n\nОтправьте новую цену (например: <code>900 ₽</code>) или «отмена»." % (sv["title"], sv["price"]))
    if data.startswith("svc:"):
        return show_service(chat_id, data[4:])
    if data.startswith("buy:"):
        return handle_buy(chat_id, user, data[4:])
    return show_menu(chat_id)


def handle_update(update):
    try:
        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as e:
        print("Handler error:", e)


# ---------- сервер ----------
@app.route("/")
def index():
    return "Bot is alive"


@app.route("/health")
def health():
    return "ok"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    handle_update(update)
    return jsonify(ok=True)


@app.route("/setwebhook")
def set_webhook():
    url = request.args.get("url") or request.host_url.rstrip("/") + "/webhook"
    return jsonify(api("setWebhook", url=url, drop_pending_updates=True))


@app.route("/delwebhook")
def del_webhook():
    return jsonify(api("deleteWebhook", drop_pending_updates=True))


def polling():
    offset = 0
    print("Polling started")
    while True:
        try:
            r = requests.get(
                BASE + "/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            ).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_update(upd)
        except Exception as e:
            print("Polling error:", e)
            time.sleep(3)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    if POLLING:
        threading.Thread(target=polling, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
