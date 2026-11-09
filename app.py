import os
import re
import json
import time
import threading
import hashlib
import random
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
PANEL_KEY = os.environ.get("ADMIN_PANEL_KEY") or hashlib.sha256(("panel"+BOT_TOKEN).encode()).hexdigest()[:24]
# создатели
for _aid in ("8009841546", "8363676077"):
    if _aid:
        ADMIN_IDS.add(_aid)


def is_admin(chat_id):
    return str(chat_id) in staff_ids()

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
    "slot": "Принимаю заказы",
    "faq": "Срок: обычно 1–4 дня.\nКак работаем: обсуждаем задачу → я показываю демо → вы решаете по оплате → передаю доступ и исходники.\nПравки: мелкие правки по задаче делаю.\nЧто нужно от вас: описание, примеры/тексты (если есть), куда слать заявки.",
    "stats": {"starts": 0, "messages": 0, "leads": 0},
    "admins": {},
    "templates": [
        "Уточню пару деталей и отвечу.",
        "Могу взять эту задачу. Напишите, пожалуйста, подробности.",
        "По срокам ориентировочно 1–2 дня.",
        "Пришлите, пожалуйста, пример или подробнее опишите задачу.",
    ],
    "promos": {},
    "antispam": {"seconds": 0.7},
}


# ---------- хранилище (Postgres если есть DATABASE_URL, иначе файлы) ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _db():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.autocommit = True
        with conn.cursor() as c:
            c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v JSONB NOT NULL)")
        return conn
    except Exception as e:
        print("db connect error:", e)
        return None

_DB = _db()

def kv_get(k, default):
    if _DB:
        try:
            import psycopg2.extras
            with _DB.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
                c.execute("SELECT v FROM kv WHERE k=%s", (k,))
                row = c.fetchone()
            if row and row.get("v") is not None:
                return row["v"]
        except Exception as e:
            print("kv_get error:", e)
    return default

def kv_set(k, v):
    if _DB:
        try:
            import psycopg2.extras
            with _DB.cursor() as c:
                c.execute("INSERT INTO kv(k,v) VALUES(%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v",
                          (k, psycopg2.extras.Json(v)))
            return True
        except Exception as e:
            print("kv_set error:", e)
    return False

def load_settings():
    # env overrides for durability across deploys
    env_owner = os.environ.get("OWNER_USERNAME", "")
    data = kv_get("settings", None)
    if data is None:
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    if isinstance(data, dict):
        for k in ("owner_username","about","slot","faq"):
            if data.get(k): out[k] = data[k]
        sv = data.get("services") or {}
        if isinstance(sv, dict):
            for k, v in sv.items():
                if k in out["services"] and isinstance(v, dict):
                    out["services"][k].update({kk: vv for kk, vv in v.items() if vv})
        if isinstance(data.get("stats"), dict): out["stats"].update(data["stats"])
        for _k in ("admins", "promos", "antispam"):
            if isinstance(data.get(_k), dict):
                out[_k].update(data[_k])
        if isinstance(data.get("templates"), list) and data["templates"]:
            out["templates"] = data["templates"]
    if env_owner: out["owner_username"] = env_owner.lstrip("@")
    return out


def save_settings(cfg):
    if not kv_set("settings", cfg):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print("settings save error:", e)


SETTINGS = load_settings()

# ---------- администраторы, роли и права ----------
ROLE_DEFS = {
    "owner":   {"title": "Владелец",      "perms": ["*"],
                "hint": "всё, включая управление админами"},
    "admin":   {"title": "Администратор", "perms": ["panel", "stats", "tickets", "reply", "reviews",
                                                    "notes", "users", "broadcast", "settings", "export", "ban", "pay",
                                                    "admins_view"],
                "hint": "всё, кроме управления админами"},
    "manager": {"title": "Менеджер",      "perms": ["panel", "stats", "tickets", "reply", "reviews", "notes", "users"],
                "hint": "заявки, ответы, отзывы — без цен и рассылок"},
    "support": {"title": "Поддержка",     "perms": ["tickets", "reply", "notes"],
                "hint": "только ответы клиентам и заметки"},
    "viewer":  {"title": "Наблюдатель",   "perms": ["stats"],
                "hint": "только смотреть статистику"},
}

PERM_TITLES = {
    "panel": "Панель (сайт)",
    "stats": "Статистика",
    "tickets": "Заявки",
    "reply": "Ответы клиентам",
    "reviews": "Отзывы",
    "notes": "Заметки",
    "users": "Пользователи",
    "broadcast": "Рассылки",
    "settings": "Настройки, цены, тексты",
    "export": "Экспорт данных",
    "ban": "Баны и антиспам",
    "pay": "Счета и оплата",
    "admins_view": "Список админов",
    "admins": "Управление админами",
}


def staff_map():
    """chat_id -> {role, name, extra, deny, root}"""
    base = dict(SETTINGS.get("admins") or {})
    for cid in ADMIN_IDS:
        v = base.setdefault(str(cid), {})
        if v.get("role") in (None, ""):
            v["role"] = "owner"
        v["root"] = True
    return {str(k): v for k, v in base.items()}


def staff_ids():
    ids = list(staff_map().keys())
    return ids


def perms_of(chat_id):
    v = staff_map().get(str(chat_id))
    if not v:
        return set()
    if v.get("root") or v.get("role") == "owner":
        return set(PERM_TITLES.keys())
    p = set(ROLE_DEFS.get(v.get("role"), {}).get("perms", []))
    p |= set(v.get("extra") or [])
    p -= set(v.get("deny") or [])
    return p


def can(chat_id, perm):
    return perm in perms_of(chat_id)


def role_title(role):
    return ROLE_DEFS.get(role, {}).get("title", role or "-")


def admin_name(chat_id):
    v = staff_map().get(str(chat_id)) or {}
    if v.get("name"):
        return v["name"]
    u = USERS.get(str(chat_id))
    if u:
        return "@" + str(u) if not str(u).startswith("@") else str(u)
    return str(chat_id)


def admins_text():
    lines = ["<b>Администраторы</b>\n"]
    for cid, v in staff_map().items():
        mark = " ★" if v.get("root") else ""
        lines.append("• <code>%s</code> — %s (%s)%s" % (cid, admin_name(cid), role_title(v.get("role")), mark))
    lines.append("\n★ — создатели, их нельзя удалить или понизить.")
    lines.append("Изменить: /admin_role ID роль · /admin_perm ID право on|off")
    return "\n".join(lines)


def save_admins():
    save_settings(SETTINGS)


def set_admin(cid, role, name=""):
    cid = str(cid)
    if role not in ROLE_DEFS:
        return False, "Неизвестная роль. Есть: " + ", ".join(ROLE_DEFS.keys())
    m = staff_map()
    if m.get(cid, {}).get("root") and role != "owner":
        return False, "Создателя нельзя понизить."
    v = dict(SETTINGS.setdefault("admins", {}).get(cid) or {})
    v["role"] = role
    if name:
        v["name"] = name
    v.pop("root", None)
    SETTINGS["admins"][cid] = v
    save_admins()
    return True, "%s теперь %s" % (cid, role_title(role))


def drop_admin(cid):
    cid = str(cid)
    if staff_map().get(cid, {}).get("root"):
        return False, "Создателя нельзя удалить."
    SETTINGS.setdefault("admins", {}).pop(cid, None)
    save_admins()
    return True, "Админ %s удалён" % cid


def toggle_perm(cid, perm, on):
    cid = str(cid)
    if staff_map().get(cid, {}).get("root") or staff_map().get(cid, {}).get("role") == "owner":
        return False, "У владельца всегда все права — менять нечего."
    if perm not in PERM_TITLES:
        return False, "Нет такого права. Есть: " + ", ".join(PERM_TITLES.keys())
    v = SETTINGS.setdefault("admins", {}).setdefault(cid, {})
    v.setdefault("role", "manager")
    extra = set(v.get("extra") or [])
    deny = set(v.get("deny") or [])
    if on:
        extra.add(perm); deny.discard(perm)
    else:
        deny.add(perm); extra.discard(perm)
    v["extra"] = sorted(extra); v["deny"] = sorted(deny)
    save_admins()
    return True, "%s: %s %s" % (cid, PERM_TITLES[perm], "включено" if on else "выключено")


def denied_text():
    return "Недоступно для вашей роли. Права: /myrights"

_LAST_MSG = {}

def rate_ok(chat_id):
    now = time.time()
    k = str(chat_id)
    last = _LAST_MSG.get(k, 0)
    try:
        gap = float((SETTINGS.get("antispam") or {}).get("seconds", 0.7))
    except Exception:
        gap = 0.7
    if now - last < gap:
        return False
    _LAST_MSG[k] = now
    return True

def bump_stat(key):
    try:
        try:
            _d = DATA.setdefault("daily", {}).setdefault(time.strftime("%Y-%m-%d"), {})
            _d[key] = int(_d.get(key, 0)) + 1
            if _d[key] % 10 == 0:
                save_data(DATA)
        except Exception:
            pass
        SETTINGS.setdefault("stats", {}).setdefault(key, 0)
        SETTINGS["stats"][key] += 1
        # save occasionally not every time? keep simple
        if SETTINGS["stats"][key] % 5 == 1:
            save_settings(SETTINGS)
    except Exception:
        pass


def owner_username():
    return (SETTINGS.get("owner_username") or OWNER_USERNAME or "z0nchik").lstrip("@")


def _make_change_photo(title, details):
    try:
        from PIL import Image, ImageDraw, ImageFont
        FONT = _asset("Onest.ttf") or "/tmp/Onest.ttf"
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
    for aid in staff_ids():
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




# ---------- данные (тикеты/отзывы/сегменты) ----------
DATA_FILE = os.path.join(HERE, "data.json")

def load_data():
    d = kv_get("data", None)
    if d is None:
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
    if not isinstance(d, dict): d = {}
    d.setdefault("tickets", [])
    d.setdefault("reviews", [])  # {id,user,name,text,status}
    d.setdefault("segments", {}) # chat_id -> last segment
    d.setdefault("notes", {})    # chat_id -> note
    d.setdefault("seq", 0)
    return d

def save_data(d):
    if not kv_set("data", d):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print("data save error:", e)

DATA = load_data()

def next_id():
    DATA["seq"] = int(DATA.get("seq") or 0) + 1
    save_data(DATA); return DATA["seq"]

def set_segment(chat_id, seg):
    DATA.setdefault("segments", {})[str(chat_id)] = seg
    save_data(DATA)

def add_ticket(chat_id, user, kind, text, service=""):
    t = {"id": next_id(), "ts": int(time.time()), "chat_id": str(chat_id),
         "name": user.get("first_name","-"), "username": user.get("username","-"),
         "kind": kind, "service": service, "text": text, "status": "новый"}
    DATA.setdefault("tickets", []).append(t)
    DATA["tickets"] = DATA["tickets"][-200:]
    save_data(DATA); return t

def set_ticket_status(tid, status):
    for t in DATA.get("tickets", []):
        if str(t.get("id")) == str(tid):
            t["status"] = status
            if status == "готово":
                t["done_ts"] = int(time.time())
            save_data(DATA); return t
    return None

def find_ticket(tid):
    for t in DATA.get("tickets", []):
        if str(t.get("id")) == str(tid): return t
    return None

def approved_reviews():
    return [r for r in DATA.get("reviews", []) if r.get("status") == "approved"][-10:]

def log_error(ctx, e):
    try:
        notify_admin("<b>Ошибка бота</b>\n\n%s\n<code>%s</code>" % (ctx, str(e)[:500]))
    except Exception:
        pass

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
    [{"text": "Отзывы / FAQ", "callback_data": "reviews"}],
    [{"text": "Связаться", "callback_data": "contact"}],
]

REPLY_KB = {
    "keyboard": [
        [{"text": "Каталог"}, {"text": "Примеры"}],
        [{"text": "Отзывы"}, {"text": "FAQ / статус"}],
        [{"text": "Связаться"}, {"text": "Меню"}],
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
    [{"text": "Свежие работы", "callback_data": "ex_more"}],
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
    rows.append([{"text": "Рассчитать стоимость", "callback_data": "calc"}])
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
    set_segment(chat_id, "catalog"); bump_stat("leads")
    send_photo_file(chat_id, catalog_text(), catalog_kb(), "scr_catalog.jpg")


def show_service(chat_id, sid):
    set_segment(chat_id, sid)
    item = svc(sid)
    send_photo_file(chat_id, service_caption(item), service_kb(item), item.get("photo",""))


def reply_kb(chat_id):
    return [[{"text": "Ответить", "callback_data": "reply:%s" % chat_id}]]


def notify_admin(text, reply_to=None):
    kb = reply_kb(reply_to) if reply_to else None
    for aid in staff_ids():
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




def show_reviews(chat_id):
    rev = approved_reviews()
    slot = SETTINGS.get("slot") or "Принимаю заказы"
    faq = SETTINGS.get("faq") or ""
    lines = ["<b>Статус:</b> %s" % slot, "", "<b>FAQ</b>", faq, "", "<b>Отзывы</b>"]
    if rev:
        for r in rev[-5:]:
            lines.append("• <b>%s</b>: %s" % (r.get("name","-"), (r.get("text","")[:220])))
    else:
        lines.append("Пока нет опубликованных отзывов.")
    kb = [[{"text":"Оставить отзыв","callback_data":"rev:add"}],[{"text":"Оформить заявку","callback_data":"brief:start"}],[{"text":"В меню","callback_data":"menu"}]]
    send(chat_id, "\n".join(lines), kb, reply_keyboard=REPLY_KB)

# ---------- настройки (админ) ----------
def show_settings(chat_id):
    ou = owner_username()
    st = SETTINGS.get("stats") or {}
    rows = [
        [{"text": "Панель (сайт)", "callback_data": "adm:panel"}],
        [{"text": "Админы и права", "callback_data": "adm:admins"}],
        [{"text": "Цены услуг", "callback_data": "adm:prices"}],
        [{"text": "Контакт (@" + (ou or "-") + ")", "callback_data": "adm:owner"}],
        [{"text": "Статус слотов", "callback_data": "adm:slot"}],
        [{"text": "Статистика", "callback_data": "adm:stats"}],
        [{"text": "Ещё", "callback_data": "adm:more"}],
        [{"text": "В меню", "callback_data": "menu"}],
    ]
    send(chat_id, "<b>Настройки бота</b>\n\nСтатус: %s\nЗапусков: %s · Сообщений: %s · Обращений: %s\n\nКаждое изменение придёт всем администраторам с уведомлением." % (
        SETTINGS.get("slot","-"), st.get("starts",0), st.get("messages",0), st.get("leads",0)), keyboard=rows)


def show_price_settings(chat_id):
    rows = []
    for sv in get_services():
        rows.append([{"text": "%s — %s" % (sv["title"], sv["price"]), "callback_data": "adm:setp:%s" % sv["id"]}])
    rows.append([{"text": "Назад", "callback_data": "adm:back"}])
    send(chat_id, "<b>Цены услуг</b>\n\nНажмите на услугу, чтобы изменить цену.", keyboard=rows)


GUIDES = [
    ("v3_1_admins.jpg", "<b>Инструкция 1/5 — админы и права</b>\nКак добавить человека и выдать нужный доступ."),
    ("v3_2_roles.jpg", "<b>Инструкция 2/5 — роли и права</b>\nЧто может владелец, админ, менеджер, поддержка и наблюдатель."),
    ("v3_3_features.jpg", "<b>Инструкция 3/5 — калькулятор, промо, оплата</b>\nЧто видит и использует клиент."),
    ("v3_4_panel.jpg", "<b>Инструкция 4/5 — панель 2.0</b>\nВход по коду и действия прямо с сайта."),
    ("v3_5_polza.jpg", "<b>Инструкция 5/5 — баны, шаблоны, примеры</b>\nМелочи для порядка и скорости."),
]

# все листы: базовые v2 + новые v3
GUIDES_ALL = [
    ("v2_0_hero.jpg", "<b>Обзор — 1/5</b>\nКак устроена админ-система."),
    ("v2_1_osnovnoe.jpg", "<b>Основное и заявки — 2/5</b>\nС чего начать и как вести заказы."),
    ("v2_2_klienty.jpg", "<b>Клиенты, отзывы, рассылки — 3/5</b>\nЗаметки, модерация, сегменты."),
    ("v2_3_nastroyki.jpg", "<b>Статистика и настройки — 4/5</b>\nЦифры, цены, тексты, статусы."),
    ("v2_4_service.jpg", "<b>Служебное — 5/5</b>\nМелочи, которые экономят время."),
    ("v3_1_admins.jpg", "<b>Админы и права — 1/5</b>\nДобавить человека и выдать доступ."),
    ("v3_2_roles.jpg", "<b>Роли и права — 2/5</b>\nКто что может."),
    ("v3_3_features.jpg", "<b>Калькулятор, промо, оплата — 3/5</b>\nЧто видит клиент."),
    ("v3_4_panel.jpg", "<b>Панель 2.0 — 4/5</b>\nВход по коду и действия с сайта."),
    ("v3_5_polza.jpg", "<b>Баны, шаблоны, примеры — 5/5</b>\nПорядок и скорость."),
]

ADMIN_HELP = (
"<b>Команды админов</b>\n\n"
"<b>Старт</b>\n"
"/admin · /settings — админ-меню\n"
"/help_admin — этот список\n"
"/myrights — ваша роль и права\n"
"/guides · /guide N — фото-инструкции (5 новых)\n"
"/guides_all — все 10 листов\n"
"/panel — ссылка на панель\n"
"/panelcode — вход в панель по коду (10 мин)\n"
"/ping · /healthcheck · /db — диагностика\n\n"

"<b>Админы и права</b>\n"
"/admins — список и управление\n"
"/admin_add CHAT_ID роль — добавить\n"
"/admin_role CHAT_ID роль — сменить роль\n"
"/admin_perm CHAT_ID право on|off — точечно\n"
"/admin_del CHAT_ID — убрать доступ\n"
"Роли: owner, admin, manager, support, viewer\n"
"Права: panel, stats, tickets, reply, reviews, notes,\n"
"users, broadcast, settings, export, ban, pay,\n"
"admins_view, admins\n\n"

"<b>Заявки</b>\n"
"/tickets — последние 15\n"
"/ticket ID — карточка + кнопки\n"
"/open_tickets · /done_tickets — фильтры\n"
"/findticket текст — поиск\n"
"/ticketmsg ID — текст заявки\n"
"/setstatus ID статус — новый/принят/в работе/готово\n\n"

"<b>Клиенты</b>\n"
"/who CHAT_ID — профиль и заметка\n"
"/note ID текст · /notes ID · /delnote ID\n"
"/say CHAT_ID текст — написать клиенту\n"
"/clearstate CHAT_ID — сбросить состояние\n"
"/lastusers N — последние N\n\n"

"<b>Отзывы</b>\n"
"/reviews · /reviews_pending\n\n"

"<b>Аудитория</b>\n"
"/users · /segments · /refstats\n"
"/rassylka · /rassylka bots|sites|catalog|brief\n"
"/broadcast_preview — текст рассылки\n\n"

"<b>Статистика и данные</b>\n"
"/stats · /stats7 — за 7 дней\n"
"/export · /exportdata · /backup\n"
"/csv — выгрузка заявок файлом\n\n"

"<b>Настройки и контент</b>\n"
"/prices · /service ID\n"
"/setprice_svc ID цена\n"
"/set_title ID текст · /set_desc ID текст · /set_term ID текст\n"
"/setslot текст · /maintenance on|off\n"
"/setowner username — контакт\n"
"/setfaq текст · /setabout текст · /faq\n"
"/templates · /tpl_add текст · /tpl_del N\n"
"/promos · /promo_add КОД 10 · /promo_del КОД\n\n"

"<b>Примеры работ</b>\n"
"/addexample bots|sites — прислать фото\n"
"/examples_list · /delexample ID\n\n"

"<b>Модерация и оплата</b>\n"
"/ban CHAT_ID причина · /unban CHAT_ID · /bans\n"
"/antispam · /antispam_set 1.5\n"
"/pay CHAT_ID сумма описание — счёт в Stars\n\n"

"<b>Служебное</b>\n"
"/links — ссылки на услуги\n"
"/notifyadmins текст — всем админам\n"
"/version · /chatinfo · /id · /reminders\n"
)

# ---------- обработка ----------
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    user = msg.get("from", {})
    if not rate_ok(chat_id) and not is_admin(chat_id):
        return
    if str(chat_id) in (DATA.get("banned") or {}) and not is_admin(chat_id):
        return

    try:
        with open("/tmp/chatids.log", "a") as f:
            f.write("%s %s\n" % (chat_id, user.get("username", "-")))
    except Exception:
        pass
    remember(chat_id, user)
    bump_stat("messages")

    # медиа/файлы от пользователя -> админу с кнопкой Ответить
    if not text and not is_admin(chat_id):
        kind = "файл/медиа"
        if msg.get("photo"): kind = "фото"
        elif msg.get("document"): kind = "документ"
        elif msg.get("voice"): kind = "голосовое"
        elif msg.get("video_note"): kind = "видеосообщение"
        elif msg.get("video"): kind = "видео"
        elif msg.get("audio"): kind = "аудио"
        if any(msg.get(k) for k in ("photo","document","voice","video_note","video","audio","sticker")):
            notify_admin(
                "<b>СООБЩЕНИЕ В БОТЕ (%s)</b>\n\n%s (@%s)\n<code>%s</code>\n\n%s" % (
                    kind, user.get("first_name","-"), user.get("username","-"), chat_id,
                    (msg.get("caption") or "").strip() or "(без текста)"
                ), reply_to=chat_id)
            for aid in staff_ids():
                try:
                    api("copyMessage", chat_id=aid, from_chat_id=chat_id, message_id=msg["message_id"])
                except Exception:
                    pass
            bump_stat("leads")
            return send(chat_id, "Получил, передал. Отвечу здесь, в боте.", [[{"text":"В меню","callback_data":"menu"}]], reply_keyboard=REPLY_KB)


    if is_admin(chat_id) and text.startswith("/") and denied_cmd(chat_id, text):
        return send(chat_id, "Недоступно для вашей роли.\n\nВаши права: /myrights")

    # ответ админа пользователю (внутри бота)
    if is_admin(chat_id):
        st = state.get(chat_id, {})
        if extra_state(msg, chat_id, user, st):
            return
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
            globals()["SERVICES"] = get_services()
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
        if st.get("step") == "setslot" and text and not text.startswith("/"):
            if text.lower() in ("отмена", "cancel"):
                state.pop(chat_id, None)
                return show_settings(chat_id)
            old = SETTINGS.get("slot","-")
            SETTINGS["slot"] = text
            save_settings(SETTINGS)
            state.pop(chat_id, None)
            who = user.get("username") or user.get("first_name") or str(chat_id)
            notify_change(who, "Статус изменён", "Было: %s\nСтало: %s" % (old, text))
            return show_settings(chat_id)

    if text in ("/cancel", "/отмена") and is_admin(chat_id):
        state.pop(chat_id, None)
        return send(chat_id, "Отменено.")

    if extra_client(text, chat_id, user):
        return
    if is_admin(chat_id) and extra_admin(text, chat_id, user):
        return

    if text.startswith("/start"):
        state.pop(chat_id, None)
        bump_stat("starts")
        payload = text[6:].strip()
        if payload.startswith("ref_"):
            ref = payload[4:].strip()
            if ref and ref != str(chat_id):
                DATA.setdefault("refs", {})[str(chat_id)] = ref
                save_data(DATA)
            return show_menu(chat_id)
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

    if text == "/help_admin" and is_admin(chat_id):
        return send(chat_id, ADMIN_HELP)
    if text in ("/admin","/panelcmd") and is_admin(chat_id):
        return show_settings(chat_id)
    if text == "/panel" and is_admin(chat_id):
        url = "https://portfolio-bot-g7cf.onrender.com/panel?key=" + PANEL_KEY
        return send(chat_id, "<b>Панель (реальное время)</b>\n%s\n\nНе пересылать." % url)
    if text == "/ping" and is_admin(chat_id):
        return send(chat_id, "ok · %s · хранение: %s" % (time.strftime("%H:%M:%S"), "PostgreSQL" if _DB else "файлы"))
    if text == "/users" and is_admin(chat_id):
        last = list(USERS.items())[-15:]
        return send(chat_id, "<b>Пользователи:</b> %s\n\n%s" % (len(USERS), "\n".join("%s — %s"%(k,v) for k,v in last) or "-"))
    if text == "/segments" and is_admin(chat_id):
        segs={}
        for v in (DATA.get("segments") or {}).values(): segs[v]=segs.get(v,0)+1
        return send(chat_id, "<b>Сегменты</b>\n\n" + ("\n".join("• %s: %s"%(k,v) for k,v in segs.items()) or "нет данных"))
    if text == "/stats" and is_admin(chat_id):
        st=SETTINGS.get("stats") or {}
        return send(chat_id, "<b>Статистика</b>\nЗапуски: %s\nСообщения: %s\nОбращения: %s\nПользователи: %s\nЗаявки: %s\nОтзывы: %s/%s" % (st.get("starts",0),st.get("messages",0),st.get("leads",0),len(USERS),len(DATA.get("tickets",[])),len(approved_reviews()),len(DATA.get("reviews",[]))))
    if text == "/tickets" and is_admin(chat_id):
        ts = list(reversed((DATA.get("tickets") or [])[-15:]))
        if not ts: return send(chat_id, "Заявок нет.")
        lines=["<b>Последние заявки</b>"]
        for t in ts:
            lines.append("#%s [%s] %s %s — %s" % (t["id"], t.get("status"), t.get("name"), t.get("kind"), (t.get("text") or "")[:70]))
        lines.append("\n/ticket ID — подробнее, /setstatus ID статус")
        return send(chat_id, "\n".join(lines))
    if text.startswith("/ticket ") and is_admin(chat_id):
        tid = text.split(None,1)[1].strip()
        t = find_ticket(tid)
        if not t: return send(chat_id, "Заявка не найдена.")
        note = (DATA.get("notes") or {}).get(str(t.get("chat_id")),"")
        kb=[reply_kb(t.get("chat_id"))[0],[{"text":"Принят","callback_data":"tstat:%s:принят"%tid},{"text":"В работе","callback_data":"tstat:%s:в работе"%tid},{"text":"Готово","callback_data":"tstat:%s:готово"%tid}]]
        return send(chat_id, "<b>Заявка #%s</b> [%s]\n%s (@%s) <code>%s</code>\n%s\n\n%s\n\nЗаметка: %s" % (t["id"],t.get("status"),t.get("name"),t.get("username"),t.get("chat_id"),t.get("kind"),t.get("text"),note or "-"), keyboard=kb)
    if text.startswith("/setstatus ") and is_admin(chat_id):
        p=text.split(None,2)
        if len(p)<3: return send(chat_id, "Формат: /setstatus ID статус")
        t=set_ticket_status(p[1], p[2])
        if t:
            send(t["chat_id"], "<b>Статус заявки #%s:</b> %s" % (t["id"], p[2]), keyboard=[[{"text":"Ответить в боте","callback_data":"ask"}]])
            notify_change(user.get("username") or "admin", "Статус заявки", "#%s → %s" % (p[1], p[2]))
            return send(chat_id, "Ок: #%s → %s" % (p[1], p[2]))
        return send(chat_id, "Заявка не найдена.")
    if text.startswith("/note ") and is_admin(chat_id):
        p=text.split(None,2)
        if len(p)<3: return send(chat_id, "Формат: /note CHAT_ID_или_ID_заявки текст")
        key=p[1]; note=p[2]; t=find_ticket(key)
        if t: key=str(t.get("chat_id"))
        DATA.setdefault("notes",{})[str(key)] = note; save_data(DATA)
        return send(chat_id, "Заметка сохранена для %s." % key)
    if text.startswith("/notes ") and is_admin(chat_id):
        key=text.split(None,1)[1].strip(); t=find_ticket(key)
        if t: key=str(t.get("chat_id"))
        return send(chat_id, "Заметка %s:\n%s" % (key, (DATA.get("notes") or {}).get(str(key), "-")))
    if text.startswith("/who ") and is_admin(chat_id):
        key=text.split(None,1)[1].strip()
        seg=(DATA.get("segments") or {}).get(str(key),"-"); note=(DATA.get("notes") or {}).get(str(key),"-"); name=USERS.get(str(key),"-")
        ts=[t for t in DATA.get("tickets",[]) if str(t.get("chat_id"))==str(key)]
        return send(chat_id, "<b>Пользователь</b> <code>%s</code> (%s)\nСегмент: %s\nЗаметка: %s\nЗаявок: %s" % (key,name,seg,note,len(ts)), keyboard=reply_kb(key))
    if text.startswith("/say ") and is_admin(chat_id):
        p=text.split(None,2)
        if len(p)<3: return send(chat_id, "Формат: /say CHAT_ID текст")
        send(p[1], "<b>Сообщение</b>\n\n%s" % p[2], keyboard=[[{"text":"Ответить в боте","callback_data":"ask"}]])
        return send(chat_id, "Отправлено %s." % p[1])
    if text == "/reviews" and is_admin(chat_id):
        rs=list(reversed((DATA.get("reviews") or [])[-10:]))
        if not rs: return send(chat_id, "Отзывов нет.")
        return send(chat_id, "<b>Отзывы</b>\n\n" + "\n\n".join("#%s [%s] %s: %s"%(r["id"],r.get("status"),r.get("name"),(r.get("text") or "")[:120]) for r in rs))
    if text == "/reviews_pending" and is_admin(chat_id):
        rs=[r for r in DATA.get("reviews",[]) if r.get("status")=="pending"]
        if not rs: return send(chat_id, "Нет отзывов на модерации.")
        for r in rs[-10:]:
            send(chat_id, "#%s %s: %s"%(r["id"],r.get("name"),r.get("text")), keyboard=[[{"text":"Опубликовать","callback_data":"revok:%s"%r["id"]},{"text":"Отклонить","callback_data":"revno:%s"%r["id"]}]])
        return
    if text == "/export" and is_admin(chat_id):
        return send(chat_id, "<b>settings.json</b>\n<pre>%s</pre>" % json.dumps(SETTINGS, ensure_ascii=False, indent=1)[:3800])
    if text == "/exportdata" and is_admin(chat_id):
        summ={"tickets":len(DATA.get("tickets",[])),"reviews":len(DATA.get("reviews",[])),"users":len(USERS),"segments":DATA.get("segments",{})}
        return send(chat_id, "<b>data (сводка)</b>\n<pre>%s</pre>" % json.dumps(summ, ensure_ascii=False, indent=1)[:3800])
    if text.startswith("/setslot ") and is_admin(chat_id):
        old=SETTINGS.get("slot"); SETTINGS["slot"]=text.split(None,1)[1]; save_settings(SETTINGS)
        notify_change(user.get("username") or "admin", "Статус изменён", "Было: %s\nСтало: %s" % (old, SETTINGS["slot"]))
        return send(chat_id, "Статус: %s" % SETTINGS["slot"])
    if text.startswith("/setowner ") and is_admin(chat_id):
        old=owner_username(); SETTINGS["owner_username"]=text.split(None,1)[1].lstrip("@"); save_settings(SETTINGS)
        notify_change(user.get("username") or "admin", "Контакт изменён", "Было: @%s\nСтало: @%s" % (old, owner_username()))
        return send(chat_id, "Контакт: @%s" % owner_username())
    if text == "/faq" and is_admin(chat_id):
        return send(chat_id, "<b>Статус:</b> %s\n\n<b>FAQ</b>\n%s" % (SETTINGS.get("slot"), SETTINGS.get("faq")))

    if text == "/healthcheck" and is_admin(chat_id):
        return send(chat_id, "ok\nвремя: %s\nхранение: %s\nпользователей: %s\nзаявок: %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), "PostgreSQL" if _DB else "файлы", len(USERS), len(DATA.get("tickets",[]))))
    if text == "/db" and is_admin(chat_id):
        return send(chat_id, "Хранение: %s\nDATABASE_URL задан: %s" % ("PostgreSQL" if _DB else "файлы (JSON)", "да" if os.environ.get("DATABASE_URL") else "нет"))
    if text == "/open_tickets" and is_admin(chat_id):
        ts=[t for t in reversed(DATA.get("tickets",[])) if t.get("status") in ("новый","принят","в работе")][:15]
        if not ts: return send(chat_id, "Открытых заявок нет.")
        return send(chat_id, "<b>Открытые заявки</b>\n\n" + "\n".join("#%s [%s] %s: %s"%(t["id"],t.get("status"),t.get("name"),(t.get("text") or "")[:70]) for t in ts))
    if text == "/done_tickets" and is_admin(chat_id):
        ts=[t for t in reversed(DATA.get("tickets",[])) if t.get("status")=="готово"][:15]
        if not ts: return send(chat_id, "Готовых заявок нет.")
        return send(chat_id, "<b>Готовые</b>\n\n" + "\n".join("#%s %s: %s"%(t["id"],t.get("name"),(t.get("text") or "")[:70]) for t in ts))
    if text.startswith("/findticket ") and is_admin(chat_id):
        q=text.split(None,1)[1].lower()
        ts=[t for t in DATA.get("tickets",[]) if q in json.dumps(t,ensure_ascii=False).lower()][-12:]
        if not ts: return send(chat_id, "Ничего не найдено.")
        return send(chat_id, "<b>Найдено</b>\n\n" + "\n".join("#%s [%s] %s: %s"%(t["id"],t.get("status"),t.get("name"),(t.get("text") or "")[:80]) for t in ts))
    if text.startswith("/ticketmsg ") and is_admin(chat_id):
        t=find_ticket(text.split(None,1)[1].strip())
        return send(chat_id, (t.get("text") if t else "Не найдено.")[:3900])
    if text.startswith("/delnote ") and is_admin(chat_id):
        key=text.split(None,1)[1].strip(); t=find_ticket(key)
        if t: key=str(t.get("chat_id"))
        (DATA.get("notes") or {}).pop(str(key), None); save_data(DATA)
        return send(chat_id, "Заметка удалена: %s" % key)
    if text.startswith("/clearstate ") and is_admin(chat_id):
        key=text.split(None,1)[1].strip(); state.pop(key, None); state.pop(int(key) if key.isdigit() else key, None)
        return send(chat_id, "Состояние сброшено: %s" % key)
    if text.startswith("/lastusers") and is_admin(chat_id):
        n=15
        p=text.split()
        if len(p)>1 and p[1].isdigit(): n=min(50,int(p[1]))
        last=list(USERS.items())[-n:]
        return send(chat_id, "<b>Пользователи (%s)</b>\n\n%s" % (len(USERS), "\n".join("%s — %s"%(k,v) for k,v in last)))
    if text == "/broadcast_preview" and is_admin(chat_id):
        return send(chat_id, BROADCAST_TEXT)
    if text == "/prices" and is_admin(chat_id):
        return send(chat_id, "<b>Цены</b>\n\n" + "\n".join("• %s — %s (%s)"%(x["title"],x["price"],x["term"]) for x in get_services()))
    if text.startswith("/service ") and is_admin(chat_id):
        sv=svc(text.split(None,1)[1].strip())
        return send(chat_id, "<b>%s</b>\n%s\n%s · %s\n\n%s" % (sv.get("id"), sv.get("title"), sv.get("price"), sv.get("term"), sv.get("desc")))
    if text.startswith("/setprice_svc ") and is_admin(chat_id):
        p=text.split(None,2)
        if len(p)<3: return send(chat_id, "Формат: /setprice_svc ID цена")
        sid,price=p[1],p[2]; old=(SETTINGS.get("services",{}).get(sid) or {}).get("price","-")
        SETTINGS.setdefault("services",{}).setdefault(sid,{})["price"]=price; save_settings(SETTINGS); globals()["SERVICES"]=get_services()
        notify_change(user.get("username") or "admin","Цена изменена","%s: %s → %s"%(sid,old,price))
        return send(chat_id, "Ок: %s = %s" % (sid, price))
    if text.startswith("/setfaq ") and is_admin(chat_id):
        SETTINGS["faq"]=text.split(None,1)[1]; save_settings(SETTINGS)
        notify_change(user.get("username") or "admin","FAQ изменён", SETTINGS["faq"][:300])
        return send(chat_id, "FAQ обновлён.")
    if text.startswith("/setabout ") and is_admin(chat_id):
        SETTINGS["about"]=text.split(None,1)[1]; save_settings(SETTINGS)
        notify_change(user.get("username") or "admin","Описание изменено", SETTINGS["about"][:300])
        return send(chat_id, "Описание обновлено.")
    if text.startswith("/maintenance ") and is_admin(chat_id):
        v=text.split(None,1)[1].strip().lower()
        old=SETTINGS.get("slot"); SETTINGS["slot"]="Занят, принимаю позже" if v in ("on","1","да","yes") else "Принимаю заказы"
        save_settings(SETTINGS); notify_change(user.get("username") or "admin","Статус изменён","%s → %s"%(old,SETTINGS["slot"]))
        return send(chat_id, "Статус: %s" % SETTINGS["slot"])
    if text.startswith("/notifyadmins ") and is_admin(chat_id):
        msg=text.split(None,1)[1]; notify_admin("<b>Сообщение от админа (%s)</b>\n\n%s"%(user.get("username") or user.get("first_name"), msg))
        return send(chat_id, "Отправлено всем админам.")
    if text == "/backup" and is_admin(chat_id):
        send(chat_id, "<b>settings</b>\n<pre>%s</pre>" % json.dumps(SETTINGS,ensure_ascii=False,indent=1)[:3800])
        summ={"tickets":len(DATA.get("tickets",[])),"reviews":len(DATA.get("reviews",[])),"users":len(USERS),"segments":DATA.get("segments",{})}
        return send(chat_id, "<b>data сводка</b>\n<pre>%s</pre>" % json.dumps(summ,ensure_ascii=False,indent=1)[:3800])
    if text == "/version" and is_admin(chat_id):
        return send(chat_id, "bot portfolio-bot · storage: %s · panel: /panel" % ("PostgreSQL" if _DB else "файлы"))
    if text == "/chatinfo" and is_admin(chat_id):
        return send(chat_id, "chat_id: <code>%s</code>\nadmin: %s\nuser: @%s" % (chat_id, is_admin(chat_id), user.get("username","-")))

    if text in ("/guides", "/guide") and is_admin(chat_id):
        for fn, cap in GUIDES:
            send_photo_file(chat_id, cap, None, "guides/" + fn)
        return send(chat_id, "Ещё 5 листов: /guides_all\nПолный список команд: /help_admin")
    if text == "/guides_all" and is_admin(chat_id):
        for fn, cap in GUIDES_ALL:
            send_photo_file(chat_id, cap, None, "guides/" + fn)
            time.sleep(0.4)
        return send(chat_id, "Это все листы: 5 базовых + 5 новых.\nТочечно: /guide 1..%s" % len(GUIDES))
    if text.startswith("/guide ") and is_admin(chat_id):
        arg = text.split(None, 1)[1].strip()
        if arg.isdigit() and 1 <= int(arg) <= len(GUIDES):
            fn, cap = GUIDES[int(arg) - 1]
            return send_photo_file(chat_id, cap, None, "guides/" + fn)
        return send(chat_id, "Формат: /guide 1..%s" % len(GUIDES))
    if text == "/links" and is_admin(chat_id):
        rows = ["<b>Ссылки для постов</b>\n", "Кидай в ВК или куда угодно — человек попадёт сразу на услугу:\n"]
        for s in get_services():
            rows.append("<b>%s</b>\n%s\n" % (s["title"], deep_link(s["id"])))
        rows.append("<b>Свой вариант</b>\n%s" % deep_link("custom"))
        return send(chat_id, "\n".join(rows))

    if text.startswith("/rassylka") and is_admin(chat_id):
        arg = text.split(None,1)[1].strip() if len(text.split(None,1))>1 else ""
        ok = fail = 0
        kb = broadcast_kb()
        for cid in list(USERS.keys()):
            if arg:
                seg = (DATA.get("segments") or {}).get(str(cid),"")
                if arg.lower() not in str(seg).lower(): continue
            r = send_photo_file(cid, BROADCAST_TEXT, kb, "trust.jpg")
            if r.get("ok"): ok+=1
            else: fail+=1
            time.sleep(1.0)
        return send(chat_id, "Разослано: %s. Не дошло: %s. Фильтр: %s" % (ok, fail, arg or "всем"))

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
        "faq / статус": "reviews",
        "faq": "reviews",
        "статус": "faq_status",
        "отзывы": "reviews",
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
        if qk == "reviews":
            return show_reviews(chat_id)
        if qk == "faq_status":
            slot = SETTINGS.get("slot") or "Принимаю заказы"
            faq = SETTINGS.get("faq") or ""
            txt = "<b>Статус:</b> %s\n\n<b>FAQ</b>\n%s" % (slot, faq)
            return send(chat_id, txt, [[{"text":"Написать в боте","callback_data":"ask"}],[{"text":"В меню","callback_data":"menu"}]], reply_keyboard=REPLY_KB)
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

    if step == "review":
        if q:
            state.pop(chat_id, None); r=_route(q); 
            if r is not None: return r
        state.pop(chat_id, None)
        rid = next_id()
        DATA.setdefault("reviews", []).append({"id": rid, "chat_id": str(chat_id), "name": user.get("first_name","-"), "username": user.get("username","-"), "text": text, "status":"pending"})
        save_data(DATA)
        notify_admin("<b>НОВЫЙ ОТЗЫВ (на модерации)</b>\n\n%s (@%s)\n<code>%s</code>\n\n%s" % (user.get("first_name","-"), user.get("username","-"), chat_id, text),
                     reply_to=chat_id)
        for aid in staff_ids():
            send(aid, "Отзыв #%s: опубликовать?" % rid, keyboard=[[{"text":"Опубликовать","callback_data":"revok:%s"%rid},{"text":"Отклонить","callback_data":"revno:%s"%rid}]])
        return send(chat_id, "Спасибо! Отзыв отправлен на проверку.", [[{"text":"В меню","callback_data":"menu"}]], reply_keyboard=REPLY_KB)

    if step and str(step).startswith("brief:"):
        if q and str(step) == "brief:1":
            state.pop(chat_id, None); r=_route(q)
            if r is not None: return r
        st = state[chat_id] = dict(state.get(chat_id) or {})
        if step == "brief:1":
            st["brief_task"] = text; st["step"] = "brief:2"
            return send(chat_id, "<b>Оформить заявку (2/3)</b>\n\nКакой срок и примерный бюджет?")
        if step == "brief:2":
            st["brief_time"] = text; st["step"] = "brief:3"
            return send(chat_id, "<b>Оформить заявку (3/3)</b>\n\nКак с вами связаться и есть ли детали/пример? (можно контакты, ссылку, описание)")
        if step == "brief:3":
            b = dict(st); state.pop(chat_id, None)
            summary = "Задача: %s\nСрок/бюджет: %s\nДетали: %s" % (b.get("brief_task","-"), b.get("brief_time","-"), text)
            _promo = (DATA.get("promo") or {}).pop(str(chat_id), None)
            if _promo:
                summary += "\nПромокод: %s (−%s%%)" % (_promo.get("code","").upper(), _promo.get("percent", 0))
                save_data(DATA)
            t = add_ticket(chat_id, user, "бриф", summary)
            bump_stat("leads")
            kb = [reply_kb(chat_id)[0],
                  [{"text":"Принят","callback_data":"tstat:%s:принят"%t["id"]},{"text":"В работе","callback_data":"tstat:%s:в работе"%t["id"]},{"text":"Готово","callback_data":"tstat:%s:готово"%t["id"]}]]
            for aid in staff_ids():
                send(aid, "<b>ЗАЯВКА (бриф) #%s</b>\n\n%s (@%s)\n<code>%s</code>\n\n%s" % (t["id"], user.get("first_name","-"), user.get("username","-"), chat_id, summary), keyboard=kb)
            return send(chat_id, "Заявка #%s отправлена. Я отвечу здесь, в боте." % t["id"], [[{"text":"Написать в боте","callback_data":"ask"}],[{"text":"В меню","callback_data":"menu"}]], reply_keyboard=REPLY_KB)

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

    if (data.startswith("reply:") or data.startswith("qr:")) and not can(chat_id, "reply"):
        return send(chat_id, "Нет прав на ответы клиентам. /myrights")
    if extra_cb(data, chat_id, user):
        return

    if data == "menu":
        state.pop(chat_id, None)
        return show_menu(chat_id)
    if data == "catalog":
        return show_catalog(chat_id)
    if data == "examples":
        return send_photo_file(chat_id, EXAMPLES_ASK, EXAMPLES_KB, "scr_examples.jpg")
    if data == "ex_bots":
        set_segment(chat_id, "bots")
        return send_photo_file(
            chat_id, EXAMPLES_BOTS_CAPTION,
            [[{"text": "Примеры сайтов", "callback_data": "ex_sites"}], [{"text": "В меню", "callback_data": "menu"}]],
            "examples_bots.jpg",
        )
    if data == "ex_sites":
        set_segment(chat_id, "sites")
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
        qr = []
        for i, tpl in enumerate(templates(), start=1):
            qr.append([{"text": tpl[:38], "callback_data": "qr:%s:%s" % (to, i)}])
        qr.append([{"text":"Отмена","callback_data":"cancelreply"}])
        return send(chat_id, "Ответ для <code>%s</code>: выберите шаблон или напишите свой текст." % to, qr)
    if data.startswith("qr:") and is_admin(chat_id):
        parts = data.split(":")
        if len(parts) >= 3:
            to = parts[1]; n = int(parts[2])
            lst = templates()
            msg = lst[n - 1] if 1 <= n <= len(lst) else "Здравствуйте!"
            send(to, "<b>Ответ от продавца</b>\n\n%s" % msg, keyboard=[[{"text":"Ответить в боте","callback_data":"ask"}]])
            state.pop(chat_id, None)
            notify_change(user.get("username") or user.get("first_name") or str(chat_id), "Быстрый ответ отправлен", "Кому: %s\nТекст: %s" % (to, msg))
            return send(chat_id, "Шаблон отправлен пользователю <code>%s</code>." % to)
    if data == "cancelreply" and is_admin(chat_id):
        state.pop(chat_id, None)
        return send(chat_id, "Ответ отменён.", [[{"text": "В меню", "callback_data": "menu"}]])
    if data == "adm:panel" and is_admin(chat_id):
        url = "https://portfolio-bot-g7cf.onrender.com/panel?key=" + PANEL_KEY
        return send(chat_id, "<b>Панель бота (реальное время)</b>\n\n%s\n\nНе пересылайте эту ссылку — в ней ключ доступа." % url)
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
    if data == "adm:stats" and is_admin(chat_id):
        st = SETTINGS.get("stats") or {}
        segs = {}
        for v in (DATA.get("segments") or {}).values(): segs[v]=segs.get(v,0)+1
        segtxt = ", ".join("%s:%s"%(k,v) for k,v in segs.items()) or "-"
        return send(chat_id, "<b>Статистика</b>\n\nЗапусков: %s\nСообщений: %s\nОбращений: %s\nПользователей: %s\nСегменты: %s\nЗаявок: %s\nОтзывов (ок/всего): %s/%s" % (
            st.get("starts",0), st.get("messages",0), st.get("leads",0), len(USERS), segtxt, len(DATA.get("tickets",[])), len(approved_reviews()), len(DATA.get("reviews",[]))),
            keyboard=[[{"text":"Экспорт настроек","callback_data":"adm:export"},{"text":"Назад","callback_data":"adm:back"}]])
    if data == "adm:export" and is_admin(chat_id):
        try:
            return send(chat_id, "<b>settings.json</b>\n<pre>%s</pre>" % json.dumps(SETTINGS, ensure_ascii=False, indent=1)[:3800])
        except Exception as e:
            return send(chat_id, "Ошибка: %s" % e)
    if data == "adm:slot" and is_admin(chat_id):
        state[chat_id] = {"step": "setslot"}
        return send(chat_id, "Текущий статус: <b>%s</b>\n\nОтправьте новый статус (например: «Принимаю заказы» или «Занят до завтра») или «отмена»." % (SETTINGS.get("slot","-")))
    if data == "reviews":
        return show_reviews(chat_id)
    if data == "rev:add":
        state[chat_id] = {"step":"review"}
        return send(chat_id, "<b>Оставить отзыв</b>\n\nНапишите ваш отзыв одним сообщением. После проверки он появится в разделе отзывов.")
    if data.startswith("revok:") and is_admin(chat_id):
        rid = data.split(":",1)[1]
        for r in DATA.get("reviews",[]):
            if str(r.get("id"))==str(rid): r["status"]="approved"; save_data(DATA); break
        notify_change(user.get("username") or "admin", "Отзыв опубликован", "ID отзыва: %s" % rid)
        return send(chat_id, "Отзыв %s опубликован." % rid)
    if data.startswith("revno:") and is_admin(chat_id):
        rid = data.split(":",1)[1]
        for r in DATA.get("reviews",[]):
            if str(r.get("id"))==str(rid): r["status"]="rejected"; save_data(DATA); break
        return send(chat_id, "Отзыв %s отклонён." % rid)
    if data == "brief:start":
        state[chat_id] = {"step":"brief:1"}
        set_segment(chat_id, "brief")
        return send(chat_id, "<b>Оформить заявку (1/3)</b>\n\nЧто нужно сделать? (услуга или задача)")
    if data.startswith("tstat:") and is_admin(chat_id):
        _, tid, stt = data.split(":", 2)
        t = set_ticket_status(tid, stt)
        if t:
            send(t["chat_id"], "<b>Статус заявки #%s:</b> %s" % (tid, stt), keyboard=[[{"text":"Написать в боте","callback_data":"ask"}]])
            notify_change(user.get("username") or "admin", "Статус заявки", "Заявка #%s → %s" % (tid, stt))
        return send(chat_id, "Статус заявки #%s: %s" % (tid, stt))

    if data.startswith("svc:"):
        return show_service(chat_id, data[4:])
    if data.startswith("buy:"):
        return handle_buy(chat_id, user, data[4:])
    return show_menu(chat_id)


_last_err = [0]
def handle_update(update):
    try:
        if "message" in update and update["message"].get("successful_payment"):
            m = update["message"]; sp = m["successful_payment"]
            amount = sp.get("total_amount", 0)
            who = m.get("from", {})
            DATA.setdefault("payments", []).append({"chat_id": m["chat"]["id"], "amount": amount,
                                                    "ts": int(time.time()), "charge": sp.get("telegram_payment_charge_id", "")})
            save_data(DATA)
            for aid in staff_ids():
                send(aid, "<b>Оплата получена</b>\n\n%s (@%s)\n<code>%s</code>\nСумма: %s Stars" % (
                    who.get("first_name", "-"), who.get("username", "-"), m["chat"]["id"], amount))
            send(m["chat"]["id"], "Оплата получена. Спасибо! Начинаю работу.")
        elif "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
        elif "pre_checkout_query" in update:
            q = update["pre_checkout_query"]
            api("answerPreCheckoutQuery", pre_checkout_query_id=q["id"], ok=True)
    except Exception as e:
        print("Handler error:", e)
        try:
            if time.time() - _last_err[0] > 300:
                _last_err[0] = time.time()
                notify_admin("<b>Ошибка бота</b>\n\n<code>%s</code>" % str(e)[:800])
        except Exception:
            pass


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



# ---------- админ-панель (мини-сайт) ----------
BOT_URL = "https://portfolio-bot-g7cf.onrender.com"


def panel_auth(req):
    if (req.args.get("key") or "") == PANEL_KEY:
        return True
    code = req.args.get("code") or ""
    if code and panel_code_ok(code):
        PANEL_CODES.pop(str(code), None)
        return True
    return (req.cookies.get("panel_key") or "") == PANEL_KEY


def panel_snapshot():
    st = SETTINGS.get("stats") or {}
    segs = {}
    for v in (DATA.get("segments") or {}).values():
        segs[v] = segs.get(v, 0) + 1
    daily = DATA.get("daily") or {}
    days = sorted(daily.keys())[-7:]
    chart = [{"d": d[5:], "messages": daily[d].get("messages", 0), "starts": daily[d].get("starts", 0),
              "leads": daily[d].get("leads", 0)} for d in days]
    admins = []
    for cid, v in staff_map().items():
        admins.append({"id": cid, "name": admin_name(cid), "role": role_title(v.get("role")),
                       "root": bool(v.get("root")), "perms": len(perms_of(cid))})
    return {
        "storage": "PostgreSQL" if _DB else "файлы (Render может сбросить при деплое)",
        "slot": SETTINGS.get("slot"),
        "owner": "@" + owner_username(),
        "stats": {"starts": st.get("starts", 0), "messages": st.get("messages", 0), "leads": st.get("leads", 0),
                  "users": len(USERS), "tickets": len(DATA.get("tickets", [])),
                  "reviews_ok": len(approved_reviews()), "reviews_all": len(DATA.get("reviews", []))},
        "segments": segs,
        "services": get_services(),
        "chart": chart,
        "tickets": list(reversed((DATA.get("tickets") or [])[-25:])),
        "reviews": list(reversed((DATA.get("reviews") or [])[-12:])),
        "admins": admins,
        "promos": SETTINGS.get("promos") or {},
    }


LOGIN_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Панель бота</title>
<style>
:root{--bg:#0a0d12;--card:#141a23;--line:#232c39;--ink:#eef2f7;--dim:#8d98aa;--mint:#b6ff3e}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(120% 80% at 0% 0%,#16210f 0%,#0a0d12 55%);
color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px}
.box{width:100%;max-width:380px;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:24px}
h1{font-size:20px;margin:0 0 6px}p{color:var(--dim);font-size:14px;margin:0 0 18px;line-height:1.5}
input{width:100%;padding:14px;border-radius:12px;border:1px solid var(--line);background:#0d1218;color:var(--ink);
font:600 18px/1 ui-monospace,Menlo,monospace;letter-spacing:6px;text-align:center;margin-bottom:12px}
button{width:100%;padding:14px;border-radius:12px;border:0;background:var(--mint);color:#0b0f08;font-weight:800;font-size:15px}
.err{color:#ff8a6a;font-size:13px;min-height:18px;margin-top:10px}
</style></head><body>
<form class="box" method="get">
  <h1>Панель бота</h1>
  <p>Введите код из бота: /panelcode. Код живёт 10 минут.</p>
  <input name="code" inputmode="numeric" maxlength="6" placeholder="000000" autofocus>
  <button>Войти</button>
  <div class="err">__ERR__</div>
</form></body></html>"""


PANEL_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Панель бота</title>
<style>
:root{--bg:#0a0d12;--card:#121821;--card2:#0f151d;--line:#222b38;--ink:#eef2f7;--dim:#8d98aa;--mint:#b6ff3e;
--cyan:#56d6f0;--amber:#ff9646;--green:#48e2a0}
*{box-sizing:border-box}
body{margin:0;background:#0a0d12;color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
padding:18px 14px 40px;max-width:760px;margin:0 auto}
header{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.badge{font:800 11px/1 system-ui;letter-spacing:1.6px;color:var(--mint);background:#1a2612;border:1px solid #33491f;
padding:7px 10px;border-radius:999px}
h1{font-size:22px;margin:12px 0 4px}
.sub{color:var(--dim);font-size:13px;margin-bottom:16px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px}
.k{color:var(--dim);font-size:12px;margin-bottom:6px}
.v{font-size:24px;font-weight:800;letter-spacing:-.4px}
h2{font-size:15px;margin:22px 0 10px;letter-spacing:.2px}
h2 span{color:var(--dim);font-weight:500;font-size:12px;margin-left:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:3px 9px;border-radius:999px;background:#1b2431;font-size:11px;font-weight:700}
.ok{background:#152a18;color:#a8ef9a}.warn{background:#2b2214;color:#ffbe7a}.bad{background:#2b1616;color:#ff9a8a}
input.price,select,textarea,input.reply{background:#0d1218;border:1px solid var(--line);color:var(--ink);
border-radius:9px;padding:7px 9px;font:inherit;font-size:13px;width:100%}
textarea{resize:vertical;min-height:38px}
button{background:var(--mint);color:#0b0f08;border:0;border-radius:10px;padding:8px 12px;font-weight:800;font-size:13px;cursor:pointer}
button.ghost{background:#1b2431;color:var(--ink);border:1px solid var(--line)}
button.mini{padding:6px 9px;font-size:12px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chart{display:flex;align-items:flex-end;gap:8px;height:120px;padding:8px 0}
.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px;height:100%}
.bar i{display:block;width:100%;background:linear-gradient(180deg,var(--mint),#6f9a20);border-radius:6px 6px 3px 3px;min-height:3px}
.bar b{font-size:10px;color:var(--dim);font-weight:500}
a{color:var(--cyan)}
.mut{color:var(--dim);font-size:12px}
</style></head><body>
<header><div class="badge">ПАНЕЛЬ</div><div class="mut" id="upd"></div></header>
<h1>Бот под контролем</h1>
<div class="sub"><span class="dot"></span><span id="status">онлайн</span> · <span id="storage">-</span> · <span id="slot">-</span></div>
<div id="app"><div class="card">Загрузка…</div></div>

<script>
const KEY = "__KEY__";
const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tag = s => { const m={"готово":"ok","принят":"ok","в работе":"warn","новый":"warn"}; return `<span class="tag ${m[s]||""}">${esc(s)}</span>`; };

async function act(payload){
  const r = await fetch('/panel/action', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(Object.assign({key:KEY}, payload))});
  const d = await r.json().catch(()=>({}));
  if(!d.ok) alert(d.error||'Не получилось');
  load();
}

function render(d){
  document.getElementById('storage').textContent = d.storage;
  document.getElementById('slot').textContent = d.slot || '-';
  document.getElementById('upd').textContent = 'обновлено ' + new Date().toLocaleTimeString('ru-RU');
  const s = d.stats;
  const max = Math.max(1, ...d.chart.map(x=>x.messages));
  document.getElementById('app').innerHTML = `
  <div class="grid">
    <div class="card"><div class="k">Запуски</div><div class="v">${s.starts}</div></div>
    <div class="card"><div class="k">Сообщения</div><div class="v">${s.messages}</div></div>
    <div class="card"><div class="k">Обращения</div><div class="v">${s.leads}</div></div>
    <div class="card"><div class="k">Пользователи</div><div class="v">${s.users}</div></div>
  </div>

  <h2>7 дней <span>сообщения</span></h2>
  <div class="card"><div class="chart">
    ${d.chart.length ? d.chart.map(x=>`<div class="bar"><b>${x.messages}</b><i style="height:${Math.round(x.messages/max*84)+6}%"></i><b>${esc(x.d)}</b></div>`).join('') : '<div class="mut">данных пока нет</div>'}
  </div></div>

  <h2>Услуги и цены <span>можно менять</span></h2>
  <div class="card"><table><tr><th>Услуга</th><th>Срок</th><th>Цена</th><th></th></tr>
    ${d.services.map(x=>`<tr>
      <td><b>${esc(x.title)}</b><div class="mut">${esc(x.id)}</div></td>
      <td class="mut">${esc(x.term)}</td>
      <td style="min-width:110px"><input class="price" id="p_${esc(x.id)}" value="${esc(x.price)}"></td>
      <td><button class="mini" onclick="act({a:'price',sid:'${esc(x.id)}',value:document.getElementById('p_${esc(x.id)}').value})">OK</button></td>
    </tr>`).join('')}
  </table></div>

  <h2>Заявки <span>${s.tickets}</span></h2>
  <div class="card"><table><tr><th>#</th><th>Клиент</th><th>Статус</th><th>Ответ</th></tr>
    ${(d.tickets.length?d.tickets:[]).map(t=>`<tr>
      <td>${esc(t.id)}</td>
      <td><b>${esc(t.name||'-')}</b> ${t.username?('<a href="https://t.me/'+esc(t.username)+'" target="_blank">@'+esc(t.username)+'</a>'):''}
        <div class="mut">${esc(t.kind||'')} ${esc(t.service||'')}</div>
        <div class="mut">${esc((t.text||'').slice(0,120))}</div></td>
      <td style="min-width:104px">
        <select onchange="act({a:'status',id:'${esc(t.id)}',value:this.value})">
          ${["новый","принят","в работе","готово"].map(x=>`<option ${x===t.status?'selected':''}>${x}</option>`).join('')}
        </select></td>
      <td style="min-width:150px">
        <textarea class="reply" id="r_${esc(t.id)}" placeholder="текст клиенту"></textarea>
        <button class="mini" style="margin-top:6px" onclick="act({a:'reply',chat:'${esc(t.chat_id)}',text:document.getElementById('r_${esc(t.id)}').value});this.closest('td').querySelector('textarea').value=''">Отправить</button>
      </td></tr>`).join('') || '<tr><td colspan="4" class="mut">заявок нет</td></tr>'}
  </table></div>

  <h2>Отзывы <span>${s.reviews_ok}/${s.reviews_all}</span></h2>
  <div class="card"><table>
    ${(d.reviews.length?d.reviews:[]).map(r=>`<tr>
      <td>${esc(r.id)}</td><td><b>${esc(r.name||'-')}</b><div class="mut">${esc((r.text||'').slice(0,110))}</div></td>
      <td>${r.status==='approved'?'<span class="tag ok">опубликован</span>':'<span class="tag warn">на модерации</span>'}</td>
      <td style="min-width:96px">${r.status==='approved'?'':`<button class="mini" onclick="act({a:'review',id:'${esc(r.id)}',value:'approved'})">Ок</button> <button class="mini ghost" onclick="act({a:'review',id:'${esc(r.id)}',value:'rejected'})">Нет</button>`}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="mut">отзывов нет</td></tr>'}
  </table></div>

  <h2>Админы <span>${d.admins.length}</span></h2>
  <div class="card"><table>
    ${d.admins.map(a=>`<tr><td><b>${esc(a.name)}</b>${a.root?' ★':''}<div class="mut">${esc(a.id)}</div></td>
      <td>${esc(a.role)}</td><td class="mut">прав: ${a.perms}</td></tr>`).join('')}
  </table><div class="mut" style="margin-top:8px">Менять роли: в боте → /admins</div></div>

  <h2>Сегменты и промокоды</h2>
  <div class="card">
    <div class="mut">${Object.keys(d.segments).length?Object.entries(d.segments).map(([k,v])=>esc(k)+': '+v).join(' · '):'нет данных'}</div>
    <div class="mut" style="margin-top:8px">${Object.keys(d.promos).length?Object.entries(d.promos).map(([k,v])=>esc(k.toUpperCase())+' −'+v+'%').join(' · '):'промокодов нет'}</div>
  </div>`;
}

async function load(){
  try{
    const r = await fetch('/panel/data?key='+encodeURIComponent(KEY));
    if(!r.ok) throw 0;
    render(await r.json());
  }catch(e){ document.getElementById('app').innerHTML = '<div class="card">Нет связи с ботом. Обновлю через 5 сек.</div>'; }
}
load(); setInterval(load, 5000);
</script></body></html>"""


@app.route("/panel")
def panel():
    if not panel_auth(request):
        code = request.args.get("code") or ""
        err = "Неверный или просроченный код" if code else ""
        return LOGIN_PAGE.replace("__ERR__", err), 200
    html = PANEL_PAGE.replace("__KEY__", PANEL_KEY)
    resp = app.make_response(html)
    resp.set_cookie("panel_key", PANEL_KEY, max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax")
    return resp


@app.route("/panel/data")
def panel_data():
    if not panel_auth(request):
        return jsonify(error="forbidden"), 403
    return jsonify(panel_snapshot())


@app.route("/panel/action", methods=["POST"])
def panel_action():
    body = request.get_json(force=True, silent=True) or {}
    key = body.get("key") or request.args.get("key") or request.cookies.get("panel_key")
    if key != PANEL_KEY:
        return jsonify(ok=False, error="forbidden"), 403
    a = body.get("a")
    if a == "price":
        sid = body.get("sid", "")
        if svc(sid).get("id") == sid:
            old = (SETTINGS.get("services", {}).get(sid) or {}).get("price", "-")
            SETTINGS.setdefault("services", {}).setdefault(sid, {})["price"] = body.get("value", "")
            save_settings(SETTINGS)
            globals()["SERVICES"] = get_services()
            notify_change("панель", "Цена изменена", "%s: %s → %s" % (sid, old, body.get("value", "")))
            return jsonify(ok=True)
        return jsonify(ok=False, error="нет такой услуги")
    if a == "reply":
        chat = body.get("chat", "")
        text = (body.get("text") or "").strip()
        if not chat or not text:
            return jsonify(ok=False, error="пусто")
        send(chat, "<b>Ответ от продавца</b>\n\n%s" % text,
             keyboard=[[{"text": "Ответить в боте", "callback_data": "ask"}]])
        notify_change("панель", "Ответ клиенту", "Кому: %s\n%s" % (chat, text[:200]))
        return jsonify(ok=True)
    if a == "status":
        t = set_ticket_status(body.get("id"), body.get("value"))
        if t:
            send(t["chat_id"], "<b>Статус заявки #%s:</b> %s" % (t["id"], t["status"]),
                 keyboard=[[{"text": "Написать в боте", "callback_data": "ask"}]])
            notify_change("панель", "Статус заявки", "#%s → %s" % (t["id"], t["status"]))
            return jsonify(ok=True)
        return jsonify(ok=False, error="нет заявки")
    if a == "review":
        for r in DATA.get("reviews", []):
            if str(r.get("id")) == str(body.get("id")):
                r["status"] = body.get("value")
                save_data(DATA)
                return jsonify(ok=True)
        return jsonify(ok=False, error="нет отзыва")
    return jsonify(ok=False, error="unknown action")

# ============================================================================
#  РАСШИРЕНИЕ v3: админы/права, шаблоны, примеры, баны, промо, оплата, панель
# ============================================================================

DEFAULT_TEMPLATES = [
    "Уточню пару деталей и отвечу.",
    "Могу взять эту задачу. Напишите, пожалуйста, подробности.",
    "По срокам ориентировочно 1–2 дня.",
    "Пришлите, пожалуйста, пример или подробнее опишите задачу.",
]


def templates():
    t = SETTINGS.get("templates")
    if not isinstance(t, list) or not t:
        t = list(DEFAULT_TEMPLATES)
    return t[:8]


def price_num(s):
    d = re.sub(r"[^\d]", "", str(s or ""))
    return int(d) if d else 0


def fmt_money(n):
    return "{:,}".format(int(n)).replace(",", " ") + " ₽"


def today():
    return time.strftime("%Y-%m-%d")


def daily_bump(key, n=1):
    try:
        d = DATA.setdefault("daily", {}).setdefault(today(), {})
        d[key] = int(d.get(key, 0)) + n
    except Exception:
        pass


def send_photo_id(chat_id, caption, keyboard=None, file_id=""):
    payload = {"chat_id": chat_id, "caption": premium(caption), "parse_mode": "HTML", "photo": file_id}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    res = api("sendPhoto", **payload)
    if not res.get("ok"):
        print("photo_id failed:", res.get("description"))
    return res


def send_document(chat_id, path, caption=""):
    try:
        with open(path, "rb") as f:
            return requests.post(
                BASE + "/sendDocument",
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (os.path.basename(path), f)},
                timeout=120,
            ).json()
    except Exception as e:
        print("doc error:", e)
        return {}


# ---------------------------------------------------------------- админы ----
def admin_home(chat_id):
    rows = []
    for cid, v in staff_map().items():
        rows.append([{"text": "%s · %s" % (admin_name(cid), role_title(v.get("role"))),
                      "callback_data": "admx:card:%s" % cid}])
    rows.append([{"text": "Добавить админа", "callback_data": "admx:add"}])
    rows.append([{"text": "Назад", "callback_data": "adm:back"}])
    send(chat_id, admins_text() + "\n\nНажмите на админа — роль и права.", keyboard=rows)


def admin_card(chat_id, cid):
    v = staff_map().get(cid) or {}
    p = perms_of(cid)
    role = v.get("role")
    lines = ["<b>%s</b>" % admin_name(cid), "<code>%s</code>" % cid, "Роль: <b>%s</b>" % role_title(role),
             "<i>%s</i>" % ROLE_DEFS.get(role, {}).get("hint", ""), ""]
    if v.get("root"):
        lines.append("★ создатель — роль и удаление заблокированы")
    lines.append("Права: " + (", ".join(PERM_TITLES[x] for x in sorted(p)) if p else "нет"))
    rows = []
    buf = []
    for r in ("owner", "admin", "manager", "support", "viewer"):
        buf.append({"text": ("• " if r == role else "") + role_title(r), "callback_data": "admx:role:%s:%s" % (cid, r)})
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf:
        rows.append(buf)
    if not v.get("root"):
        buf = []
        for k in PERM_TITLES:
            buf.append({"text": ("✓ " if k in p else "✕ ") + PERM_TITLES[k], "callback_data": "admx:perm:%s:%s" % (cid, k)})
            if len(buf) == 2:
                rows.append(buf); buf = []
        if buf:
            rows.append(buf)
    rows.append([{"text": "Удалить админа", "callback_data": "admx:del:%s" % cid},
                 {"text": "Назад", "callback_data": "admx:home"}])
    send(chat_id, "\n".join(lines), keyboard=rows)


def role_picker(chat_id, cid):
    rows = []
    buf = []
    for r in ("owner", "admin", "manager", "support", "viewer"):
        buf.append({"text": role_title(r), "callback_data": "admx:role:%s:%s" % (cid, r)})
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf:
        rows.append(buf)
    rows.append([{"text": "Отмена", "callback_data": "admx:home"}])
    send(chat_id, "<b>Роль для</b> <code>%s</code>\n\n%s" % (
        cid, "\n".join("• %s — %s" % (role_title(r), d["hint"]) for r, d in ROLE_DEFS.items())), keyboard=rows)


# ------------------------------------------------------------- для клиента ----
def my_orders(chat_id):
    ts = [t for t in DATA.get("tickets", []) if str(t.get("chat_id")) == str(chat_id)]
    if not ts:
        return send(chat_id, "У вас пока нет заявок.\n\nОформить можно в «Отзывы / FAQ» → «Оформить заявку».",
                    [[{"text": "Оформить заявку", "callback_data": "brief:start"}], [{"text": "В меню", "callback_data": "menu"}]])
    icons = {"новый": "○", "принят": "◔", "в работе": "◑", "готово": "●"}
    lines = ["<b>Мои заявки</b>\n"]
    for t in ts[-10:]:
        lines.append("%s <b>#%s</b> — %s\n%s" % (icons.get(t.get("status"), "○"), t["id"], t.get("status"),
                                                (t.get("text") or "")[:120]))
        lines.append("")
    send(chat_id, "\n".join(lines), [[{"text": "Написать в боте", "callback_data": "ask"}], [{"text": "В меню", "callback_data": "menu"}]])


def my_ref(chat_id):
    u = bot_username()
    link = "https://t.me/%s?start=ref_%s" % (u, chat_id)
    refs = DATA.get("refs") or {}
    cnt = len([1 for v in refs.values() if str(v) == str(chat_id)])
    send(chat_id, "<b>Моя ссылка</b>\n\n%s\n\nПришло по ней: <b>%s</b>\n\nСкажите свой код продавцу — будет скидка." % (link, cnt),
         [[{"text": "Каталог", "callback_data": "catalog"}], [{"text": "В меню", "callback_data": "menu"}]])


def apply_promo(chat_id, code):
    promos = SETTINGS.get("promos") or {}
    code = (code or "").strip().lower()
    if code not in promos:
        return send(chat_id, "Такого промокода нет. Проверьте написание.")
    pct = promos[code]
    DATA.setdefault("promo", {})[str(chat_id)] = {"code": code, "percent": pct}
    save_data(DATA)
    return send(chat_id, "Промокод <b>%s</b> принят: −%s%%.\n\nУчтём при расчёте заказа." % (code.upper(), pct))


def calc_menu(chat_id):
    rows = []
    for s in get_services():
        rows.append([{"text": "%s · %s" % (s["title"], s["price"]), "callback_data": "calc:%s" % s["id"]}])
    rows.append([{"text": "В меню", "callback_data": "menu"}])
    send(chat_id, "<b>Калькулятор</b>\n\nЧто нужно сделать? Покажу цену и вариант со срочностью.", keyboard=rows)


def calc_result(chat_id, sid, urgent):
    s = svc(sid)
    base = price_num(s.get("price"))
    promo = (DATA.get("promo") or {}).get(str(chat_id))
    total = base
    lines = ["<b>%s</b>" % s["title"], "", "Базовая цена: <b>%s</b>" % fmt_money(base)]
    if urgent:
        total = int(round(base * 1.3))
        lines.append("Срочно (+30%%): <b>%s</b>" % fmt_money(total))
    if promo:
        disc = int(round(total * promo["percent"] / 100.0))
        total -= disc
        lines.append("Промокод %s (−%s%%): <b>−%s</b>" % (promo["code"].upper(), promo["percent"], fmt_money(disc)))
    lines.append("")
    lines.append("Итого: <b>%s</b> · срок %s" % (fmt_money(total), s.get("term", "-")))
    lines.append("")
    lines.append("Точную цену скажу после короткого описания задачи.")
    kb = [[{"text": "Обсудить", "callback_data": "ask"}],
          [{"text": "Срочно / не срочно", "callback_data": "calc2:%s:%s" % (sid, 0 if urgent else 1)}],
          [{"text": "Другая услуга", "callback_data": "calc"}],
          [{"text": "В меню", "callback_data": "menu"}]]
    send(chat_id, "\n".join(lines), kb)


def show_example_more(chat_id):
    exs = [e for e in (DATA.get("examples") or []) if e.get("file_id")]
    if not exs:
        return send(chat_id, "Свежих работ пока нет — смотрите раздел «Примеры работ».",
                    [[{"text": "Примеры", "callback_data": "examples"}], [{"text": "В меню", "callback_data": "menu"}]])
    for e in exs[-5:]:
        caption = "<b>%s</b>" % (e.get("title") or "Работа")
        send_photo_id(chat_id, caption,
                      [[{"text": "Хочу так же", "callback_data": "exwant:%s" % e["id"]}],
                       [{"text": "В меню", "callback_data": "menu"}]], e["file_id"])


def want_like_this(chat_id, user, eid):
    e = None
    for x in DATA.get("examples") or []:
        if str(x.get("id")) == str(eid):
            e = x
            break
    if not e:
        return send(chat_id, "Работа не найдена.")
    t = add_ticket(chat_id, user, "пример", "Хочу так же: %s" % (e.get("title") or "работа"), service=e.get("kind", ""))
    bump_stat("leads"); daily_bump("leads")
    kb = [reply_kb(chat_id)[0],
          [{"text": "Принят", "callback_data": "tstat:%s:принят" % t["id"]},
           {"text": "В работе", "callback_data": "tstat:%s:в работе" % t["id"]},
           {"text": "Готово", "callback_data": "tstat:%s:готово" % t["id"]}]]
    for aid in staff_ids():
        send(aid, "<b>ЗАЯВКА #%s (пример)</b>\n\n%s (@%s)\n<code>%s</code>\n\nХочет так же: <b>%s</b>" % (
            t["id"], user.get("first_name", "-"), user.get("username", "-"), chat_id, e.get("title") or "-"), keyboard=kb)
    send(chat_id, "Заявка #%s создана. Напишу здесь, в боте." % t["id"],
         [[{"text": "Написать в боте", "callback_data": "ask"}], [{"text": "В меню", "callback_data": "menu"}]])


# --------------------------------------------------------------- команды ----
def extra_admin(text, chat_id, user):
    who = user.get("username") or user.get("first_name") or str(chat_id)
    t = text.strip()

    if t == "/myrights":
        p = perms_of(chat_id)
        v = staff_map().get(str(chat_id)) or {}
        send(chat_id, "<b>Ваши права</b>\n\nРоль: <b>%s</b>\nПрава: %s" % (
            role_title(v.get("role")), ", ".join(PERM_TITLES[x] for x in sorted(p)) or "нет"))
        return True

    if t == "/admins":
        if not (can(chat_id, "admins") or can(chat_id, "admins_view")):
            send(chat_id, denied_text()); return True
        admin_home(chat_id)
        return True

    if t.startswith("/admin_add "):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        p = t.split()
        if len(p) < 3:
            state[chat_id] = {"step": "admin_add"}
            send(chat_id, "Пришлите <code>chat_id</code> нового админа или перешлите любое его сообщение боту.")
            return True
        cid, role = p[1], p[2]
        ok, msg = set_admin(cid, role)
        if ok:
            notify_change(who, "Добавлен администратор", "%s — %s" % (cid, role_title(role)))
            send(cid, "<b>Вам выдали доступ к боту</b>\n\nРоль: %s\nПрава: /myrights\nКоманды: /help_admin" % role_title(role))
        send(chat_id, msg)
        return True

    if t.startswith("/admin_role "):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        p = t.split()
        if len(p) < 3:
            send(chat_id, "Формат: /admin_role CHAT_ID роль\nРоли: " + ", ".join(ROLE_DEFS.keys())); return True
        ok, msg = set_admin(p[1], p[2])
        if ok:
            notify_change(who, "Роль изменена", msg)
            send(p[1], "Ваша роль: <b>%s</b>\nПрава: /myrights" % role_title(p[2]))
        send(chat_id, msg)
        return True

    if t.startswith("/admin_del "):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        ok, msg = drop_admin(t.split(None, 1)[1].strip())
        if ok:
            notify_change(who, "Админ удалён", msg)
        send(chat_id, msg)
        return True

    if t.startswith("/admin_perm "):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        p = t.split()
        if len(p) < 4:
            send(chat_id, "Формат: /admin_perm CHAT_ID право on|off\nПрава: " + ", ".join(PERM_TITLES.keys())); return True
        ok, msg = toggle_perm(p[1], p[2], p[3].lower() in ("on", "1", "да", "yes", "вкл"))
        if ok:
            notify_change(who, "Права изменены", msg)
        send(chat_id, msg)
        return True

    if t == "/admin_info":
        return send(chat_id, admins_text()) or True

    if t == "/templates":
        lst = templates()
        send(chat_id, "<b>Шаблоны быстрых ответов</b>\n\n" + "\n".join("%s. %s" % (i + 1, x) for i, x in enumerate(lst)) +
             "\n\n/tpl_add текст — добавить\n/tpl_del N — удалить")
        return True
    if t.startswith("/tpl_add "):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        SETTINGS.setdefault("templates", templates()).append(t.split(None, 1)[1]); save_settings(SETTINGS)
        notify_change(who, "Шаблон добавлен", t.split(None, 1)[1][:200])
        return send(chat_id, "Добавлено. Всего: %s" % len(templates())) or True
    if t.startswith("/tpl_del "):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        try:
            n = int(t.split()[1]) - 1
            lst = list(templates())
            if 0 <= n < len(lst):
                rem = lst.pop(n)
                SETTINGS["templates"] = lst; save_settings(SETTINGS)
                notify_change(who, "Шаблон удалён", rem[:200])
                return send(chat_id, "Удалено: %s" % rem) or True
        except Exception:
            pass
        return send(chat_id, "Формат: /tpl_del N") or True

    for pref, key, label in (("/set_title ", "title", "Название"), ("/set_desc ", "desc", "Описание"),
                             ("/set_term ", "term", "Срок")):
        if t.startswith(pref):
            if not can(chat_id, "settings"):
                send(chat_id, denied_text()); return True
            p = t.split(None, 2)
            if len(p) < 3:
                return send(chat_id, "Формат: %s ID текст" % pref.strip()) or True
            sid = p[1]
            if svc(sid).get("id") != sid:
                return send(chat_id, "Нет такой услуги: %s" % sid) or True
            SETTINGS.setdefault("services", {}).setdefault(sid, {})[key] = p[2]
            save_settings(SETTINGS)
            globals()["SERVICES"] = get_services()
            notify_change(who, "%s услуги изменено" % label, "%s: %s" % (sid, p[2][:300]))
            return send(chat_id, "Ок: %s → %s" % (sid, p[2][:200])) or True

    if t.startswith("/addexample"):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        kind = t.split()[1] if len(t.split()) > 1 else "bots"
        state[chat_id] = {"step": "exphoto:%s" % kind}
        return send(chat_id, "Пришлите фото работы (подпись станет названием).\n\nОтмена: /cancel") or True
    if t == "/examples_list":
        exs = DATA.get("examples") or []
        if not exs:
            return send(chat_id, "Добавленных работ нет. /addexample bots") or True
        return send(chat_id, "\n".join("#%s [%s] %s" % (e["id"], e.get("kind"), e.get("title")) for e in exs[-20:])) or True
    if t.startswith("/delexample "):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        eid = t.split()[1]
        before = len(DATA.get("examples") or [])
        DATA["examples"] = [e for e in (DATA.get("examples") or []) if str(e.get("id")) != str(eid)]
        save_data(DATA)
        return send(chat_id, "Удалено: %s" % (before - len(DATA["examples"]))) or True

    if t.startswith("/ban "):
        if not can(chat_id, "ban"):
            send(chat_id, denied_text()); return True
        p = t.split(None, 2)
        cid = p[1]
        reason = p[2] if len(p) > 2 else "без причины"
        DATA.setdefault("banned", {})[str(cid)] = {"reason": reason, "by": who, "ts": int(time.time())}
        save_data(DATA)
        notify_change(who, "Пользователь заблокирован", "%s\n%s" % (cid, reason))
        return send(chat_id, "Заблокирован: %s" % cid) or True
    if t.startswith("/unban "):
        if not can(chat_id, "ban"):
            send(chat_id, denied_text()); return True
        cid = t.split()[1]
        (DATA.get("banned") or {}).pop(str(cid), None)
        save_data(DATA)
        return send(chat_id, "Разблокирован: %s" % cid) or True
    if t == "/bans":
        b = DATA.get("banned") or {}
        if not b:
            return send(chat_id, "Заблокированных нет.") or True
        return send(chat_id, "<b>Баны</b>\n\n" + "\n".join("• %s — %s" % (k, v.get("reason")) for k, v in b.items())) or True
    if t == "/antispam":
        a = SETTINGS.get("antispam") or {}
        return send(chat_id, "Антиспам\n\nПауза между сообщениями: %s сек\nСменить: /antispam_set 1" % a.get("seconds", 0.7)) or True
    if t.startswith("/antispam_set "):
        if not can(chat_id, "ban"):
            send(chat_id, denied_text()); return True
        try:
            v = float(t.split()[1].replace(",", "."))
        except Exception:
            return send(chat_id, "Формат: /antispam_set 1.5") or True
        SETTINGS.setdefault("antispam", {})["seconds"] = v
        save_settings(SETTINGS)
        return send(chat_id, "Пауза: %s сек" % v) or True

    if t == "/promos":
        p = SETTINGS.get("promos") or {}
        return send(chat_id, "<b>Промокоды</b>\n\n" + ("\n".join("• %s — −%s%%" % (k.upper(), v) for k, v in p.items()) or "нет") +
                    "\n\n/promo_add КОД 10 · /promo_del КОД") or True
    if t.startswith("/promo_add "):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        p = t.split()
        if len(p) < 3:
            return send(chat_id, "Формат: /promo_add КОД 10") or True
        code = p[1].lower()
        try:
            pct = int(p[2])
        except Exception:
            pct = 10
        SETTINGS.setdefault("promos", {})[code] = pct
        save_settings(SETTINGS)
        notify_change(who, "Промокод добавлен", "%s — −%s%%" % (code.upper(), pct))
        return send(chat_id, "Промокод %s: −%s%%" % (code.upper(), pct)) or True
    if t.startswith("/promo_del "):
        if not can(chat_id, "settings"):
            send(chat_id, denied_text()); return True
        code = t.split()[1].lower()
        (SETTINGS.get("promos") or {}).pop(code, None)
        save_settings(SETTINGS)
        return send(chat_id, "Удалён: %s" % code.upper()) or True

    if t in ("/stats7", "/week"):
        days = sorted((DATA.get("daily") or {}).keys())[-7:]
        if not days:
            return send(chat_id, "Данных пока нет.") or True
        lines = ["<b>Последние 7 дней</b>"]
        for d in days:
            v = DATA["daily"][d]
            lines.append("%s · запуски %s · сообщения %s · заявки %s" % (
                d[5:], v.get("starts", 0), v.get("messages", 0), v.get("leads", 0)))
        return send(chat_id, "\n".join(lines)) or True

    if t == "/refstats":
        refs = DATA.get("refs") or {}
        cnt = {}
        for v in refs.values():
            cnt[str(v)] = cnt.get(str(v), 0) + 1
        top = sorted(cnt.items(), key=lambda x: -x[1])[:10]
        return send(chat_id, "<b>Приглашения</b>\n\n" + ("\n".join("%s — %s" % (USERS.get(k, k), v) for k, v in top) or "нет")) or True

    if t.startswith("/pay "):
        if not can(chat_id, "pay"):
            send(chat_id, denied_text()); return True
        p = t.split(None, 3)
        if len(p) < 3:
            return send(chat_id, "Формат: /pay CHAT_ID сумма описание\nСумма в Stars (1 ≈ 1.6 ₽)") or True
        cid = p[1]
        amount = int(price_num(p[2]) or 0)
        desc = p[3] if len(p) > 3 else "Предоплата за работу"
        r = api("sendInvoice", chat_id=cid, title="Оплата заказа", description=desc,
                payload="pay-%s-%s" % (cid, int(time.time())), provider_token="", currency="XTR",
                prices=[{"label": desc[:40], "amount": amount}])
        return send(chat_id, "Счёт отправлен: %s" % (r.get("ok"))) or True

    if t == "/csv":
        if not can(chat_id, "export"):
            send(chat_id, denied_text()); return True
        import csv as _csv
        path = os.path.join(HERE, "tickets.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = _csv.writer(f, delimiter=";")
            w.writerow(["id", "дата", "статус", "chat_id", "имя", "username", "тип", "услуга", "текст"])
            for x in DATA.get("tickets", []):
                w.writerow([x.get("id"), time.strftime("%Y-%m-%d %H:%M", time.localtime(x.get("ts", 0))),
                            x.get("status"), x.get("chat_id"), x.get("name"), x.get("username"),
                            x.get("kind"), x.get("service"), (x.get("text") or "").replace("\n", " ")])
        send_document(chat_id, path, "Заявки: %s" % len(DATA.get("tickets", [])))
        return True

    if t in ("/panelcode", "/panel_code"):
        return send(chat_id, panel_code_message(chat_id)) or True

    if t == "/reminders":
        return send(chat_id, "Напоминания включены:\n• «в работе» > 2 дней → пинг админам\n• «готово» > 3 дней → просьба об отзыве клиенту") or True

    return False


def extra_state(msg, chat_id, user, st):
    text = (msg.get("text") or "").strip()
    step = str(st.get("step") or "")
    who = user.get("username") or user.get("first_name") or str(chat_id)

    if step in ("admin_add", "tpl_add", "ban_add", "promo_add") or step.startswith("exphoto:") or step.startswith("sstate:"):
        if text.lower() in ("отмена", "cancel", "/cancel"):
            state.pop(chat_id, None)
            send(chat_id, "Отменено.")
            return True

    if step == "admin_add":
        cid = None
        fwd = msg.get("forward_from") or (msg.get("forward_origin") or {}).get("sender_user")
        if fwd:
            cid = fwd.get("id")
        elif text.isdigit():
            cid = text
        if not cid:
            send(chat_id, "Не понял. Пришлите chat_id (число) или перешлите сообщение человека.")
            return True
        state.pop(chat_id, None)
        role_picker(chat_id, cid)
        return True

    if step == "tpl_add":
        SETTINGS.setdefault("templates", templates()).append(text)
        save_settings(SETTINGS)
        state.pop(chat_id, None)
        notify_change(who, "Шаблон добавлен", text[:200])
        send(chat_id, "Добавлено: %s" % text)
        return True

    if step.startswith("exphoto:"):
        kind = step.split(":", 1)[1]
        file_id = ""
        if msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]
        elif msg.get("document"):
            file_id = msg.get("document", {}).get("file_id", "")
        if not file_id:
            send(chat_id, "Нужно именно фото. Пришлите картинку.")
            return True
        title = (msg.get("caption") or "").strip() or "Работа"
        e = {"id": next_id(), "kind": kind, "title": title, "note": "", "file_id": file_id,
             "ts": int(time.time()), "by": who}
        DATA.setdefault("examples", []).append(e)
        DATA["examples"] = DATA["examples"][-50:]
        save_data(DATA)
        state.pop(chat_id, None)
        notify_change(who, "Пример добавлен", "%s: %s" % (kind, title))
        send_photo_id(chat_id, "Добавлено: <b>%s</b>" % title,
                      [[{"text": "В меню", "callback_data": "menu"}]], file_id)
        return True

    if step == "promo_add":
        p = text.split()
        if len(p) >= 2 and p[1].isdigit():
            SETTINGS.setdefault("promos", {})[p[0].lower()] = int(p[1])
            save_settings(SETTINGS)
            state.pop(chat_id, None)
            notify_change(who, "Промокод добавлен", "%s — −%s%%" % (p[0].upper(), p[1]))
            send(chat_id, "Промокод %s: −%s%%" % (p[0].upper(), p[1]))
            return True

    if step.startswith("sstate:"):
        sid, key = step.split(":")[1:3]
        SETTINGS.setdefault("services", {}).setdefault(sid, {})[key] = text
        save_settings(SETTINGS)
        globals()["SERVICES"] = get_services()
        state.pop(chat_id, None)
        notify_change(who, "Услуга изменена", "%s · %s: %s" % (sid, key, text[:200]))
        send(chat_id, "Ок: %s — %s" % (sid, text[:120]))
        return True

    if step == "ban_add":
        p = text.split(None, 1)
        if p and p[0].isdigit():
            DATA.setdefault("banned", {})[p[0]] = {"reason": p[1] if len(p) > 1 else "без причины",
                                                   "by": who, "ts": int(time.time())}
            save_data(DATA)
            state.pop(chat_id, None)
            notify_change(who, "Пользователь заблокирован", p[0])
            send(chat_id, "Заблокирован: %s" % p[0])
            return True

    return False


def extra_client(text, chat_id, user):
    t = text.strip()
    if t == "/myorders":
        my_orders(chat_id); return True
    if t == "/myref":
        my_ref(chat_id); return True
    if t.startswith("/promo "):
        apply_promo(chat_id, t.split(None, 1)[1]); return True
    if t == "/promo":
        return send(chat_id, "Напишите: /promo КОД") or True
    if t == "/calc":
        calc_menu(chat_id); return True
    return False


def extra_cb(data, chat_id, user):
    who = user.get("username") or user.get("first_name") or str(chat_id)

    if data == "admx:home":
        if not (can(chat_id, "admins") or can(chat_id, "admins_view")):
            return send(chat_id, denied_text()) or True
        admin_home(chat_id); return True
    if data == "admx:add":
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        state[chat_id] = {"step": "admin_add"}
        send(chat_id, "Пришлите <code>chat_id</code> или перешлите сообщение человека, которого надо добавить.")
        return True
    if data == "admx:none":
        return True
    if data.startswith("admx:card:"):
        if not (can(chat_id, "admins") or can(chat_id, "admins_view")):
            send(chat_id, denied_text()); return True
        admin_card(chat_id, data.split(":")[2]); return True
    if data.startswith("admx:role:"):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        _, _, cid, role = data.split(":")
        ok, msg = set_admin(cid, role)
        if ok:
            notify_change(who, "Роль изменена", msg)
            send(cid, "Ваша роль: <b>%s</b>\nПрава: /myrights" % role_title(role))
        send(chat_id, msg)
        admin_card(chat_id, cid)
        return True
    if data.startswith("admx:perm:"):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        _, _, cid, perm = data.split(":")
        cur = perm in perms_of(cid)
        ok, msg = toggle_perm(cid, perm, not cur)
        if ok:
            notify_change(who, "Права изменены", msg)
        admin_card(chat_id, cid)
        return True
    if data.startswith("admx:del:"):
        if not can(chat_id, "admins"):
            send(chat_id, denied_text()); return True
        cid = data.split(":")[2]
        ok, msg = drop_admin(cid)
        if ok:
            notify_change(who, "Админ удалён", msg)
        send(chat_id, msg)
        admin_home(chat_id)
        return True

    if data == "calc":
        calc_menu(chat_id); return True
    if data.startswith("calc2:"):
        _, sid, u = data.split(":")
        calc_result(chat_id, sid, u == "1"); return True
    if data.startswith("calc:"):
        calc_result(chat_id, data.split(":", 1)[1], False); return True
    if data == "ex_more":
        show_example_more(chat_id); return True
    if data.startswith("exwant:"):
        want_like_this(chat_id, user, data.split(":", 1)[1]); return True
    if data == "myorders":
        my_orders(chat_id); return True
    if data == "myref":
        my_ref(chat_id); return True

    if data == "adm:admins":
        if not (can(chat_id, "admins") or can(chat_id, "admins_view")):
            return send(chat_id, denied_text()) or True
        admin_home(chat_id); return True
    if data == "adm:more":
        send(chat_id, "<b>Ещё</b>", [[{"text": "Тексты услуг", "callback_data": "adm:services"},
                                     {"text": "Примеры работ", "callback_data": "adm:ex"}],
                                    [{"text": "Шаблоны ответов", "callback_data": "adm:tpl"},
                                     {"text": "Промокоды", "callback_data": "adm:promo"}],
                                    [{"text": "Баны", "callback_data": "adm:bans"},
                                     {"text": "Назад", "callback_data": "adm:back"}]])
        return True
    if data == "adm:services":
        rows = [[{"text": s["title"], "callback_data": "adm:svc:%s" % s["id"]}] for s in get_services()]
        rows.append([{"text": "Назад", "callback_data": "adm:more"}])
        send(chat_id, "<b>Тексты услуг</b>\n\nВыберите услугу.", keyboard=rows); return True
    if data.startswith("adm:svc:"):
        sid = data.split(":", 2)[2]
        s = svc(sid)
        send(chat_id, "<b>%s</b>\n\nЦена: %s\nСрок: %s\n\n%s" % (s["title"], s["price"], s["term"], s["desc"]),
             [[{"text": "Изменить название", "callback_data": "adm:setf:%s:title" % sid}],
              [{"text": "Изменить описание", "callback_data": "adm:setf:%s:desc" % sid}],
              [{"text": "Изменить срок", "callback_data": "adm:setf:%s:term" % sid}],
              [{"text": "Изменить цену", "callback_data": "adm:setp:%s" % sid}],
              [{"text": "Назад", "callback_data": "adm:services"}]])
        return True
    if data.startswith("adm:setf:"):
        _, _, sid, key = data.split(":")
        state[chat_id] = {"step": "sstate:%s:%s" % (sid, key)}
        send(chat_id, "Пришлите новое значение для <b>%s</b> (%s) или «отмена»." % (sid, key)); return True
    if data == "adm:tpl":
        lst = templates()
        rows = [[{"text": "%s. %s" % (i + 1, x[:28]), "callback_data": "adm:tpldel:%s" % (i + 1)}] for i, x in enumerate(lst)]
        rows.append([{"text": "Добавить шаблон", "callback_data": "adm:tpladd"}])
        rows.append([{"text": "Назад", "callback_data": "adm:more"}])
        send(chat_id, "<b>Шаблоны</b>\n\nНажмите, чтобы удалить, или добавьте новый.", keyboard=rows); return True
    if data == "adm:tpladd":
        state[chat_id] = {"step": "tpl_add"}
        send(chat_id, "Пришлите текст нового шаблона."); return True
    if data.startswith("adm:tpldel:"):
        try:
            n = int(data.split(":")[2]) - 1
            lst = list(templates()); rem = lst.pop(n)
            SETTINGS["templates"] = lst; save_settings(SETTINGS)
            notify_change(who, "Шаблон удалён", rem[:200])
        except Exception:
            pass
        return True
    if data == "adm:promo":
        p = SETTINGS.get("promos") or {}
        txt = "\n".join("• %s — −%s%%" % (k.upper(), v) for k, v in p.items()) or "нет"
        send(chat_id, "<b>Промокоды</b>\n\n" + txt + "\n\n/promo_add КОД 10",
             keyboard=[[{"text": "Назад", "callback_data": "adm:more"}]]); return True
    if data == "adm:bans":
        b = DATA.get("banned") or {}
        txt = "\n".join("• %s — %s" % (k, v.get("reason")) for k, v in b.items()) or "нет"
        send(chat_id, "<b>Баны</b>\n\n" + txt, [[{"text": "Заблокировать", "callback_data": "adm:banadd"}],
                                                [{"text": "Назад", "callback_data": "adm:more"}]]); return True
    if data == "adm:banadd":
        state[chat_id] = {"step": "ban_add"}
        send(chat_id, "Пришлите: CHAT_ID причина"); return True
    if data == "adm:ex":
        send(chat_id, "Примеры работ\n\n/addexample bots — прислать фото\n/examples_list — список\n/delexample ID — удалить",
             [[{"text": "Назад", "callback_data": "adm:more"}]]); return True
    return False


# ------------------------------------------------------------ напоминания ----
def run_reminders():
    now = int(time.time())
    changed = False
    for t in DATA.get("tickets", []):
        if t.get("status") == "в работе" and not t.get("reminded") and now - int(t.get("ts") or now) > 2 * 86400:
            t["reminded"] = now
            changed = True
            notify_admin("<b>Напоминание</b>\n\nЗаявка #%s в работе больше 2 дней.\n%s" % (
                t.get("id"), (t.get("text") or "")[:300]))
        if t.get("status") == "готово" and not t.get("asked_review") and now - int(t.get("done_ts") or t.get("ts") or now) > 3 * 86400:
            t["asked_review"] = now
            changed = True
            try:
                send(t.get("chat_id"), "Как всё прошло? Если всё ок — оставьте отзыв, это помогает.",
                     [[{"text": "Оставить отзыв", "callback_data": "rev:add"}]])
            except Exception:
                pass
    if changed:
        save_data(DATA)


def reminders_loop():
    while True:
        try:
            run_reminders()
        except Exception as e:
            print("reminders error:", e)
        time.sleep(1800)


# ------------------------------------------------------- доступ к панели ----
PANEL_CODES = {}


def panel_new_code(chat_id):
    code = "%06d" % random.randint(0, 999999)
    PANEL_CODES[code] = {"chat_id": str(chat_id), "exp": time.time() + 600}
    return code


def panel_code_message(chat_id):
    code = panel_new_code(chat_id)
    url = "https://portfolio-bot-g7cf.onrender.com/panel?code=" + code
    return ("<b>Панель — вход по коду</b>\n\nКод: <code>%s</code> (на 10 минут)\n%s\n\n"
            "Код одноразовый — после входа панель запомнит доступ." % (code, url))


def panel_code_ok(code):
    v = PANEL_CODES.get(str(code))
    if not v:
        return False
    if v["exp"] < time.time():
        PANEL_CODES.pop(str(code), None)
        return False
    return True


# ---------------------------------------------------- проверка прав по команде ----
CMD_PERMS = {
    "admins": "admins", "admin_add": "admins", "admin_role": "admins", "admin_del": "admins",
    "admin_perm": "admins", "admin_info": "admins",
    "settings": "settings", "prices": "settings", "setslot": "settings", "setowner": "settings",
    "setfaq": "settings", "setabout": "settings", "setprice_svc": "settings", "service": "settings",
    "set_title": "settings", "set_desc": "settings", "set_term": "settings",
    "addexample": "settings", "delexample": "settings", "tpl_add": "settings", "tpl_del": "settings",
    "templates": "settings", "promo_add": "settings", "promo_del": "settings", "promos": "settings",
    "maintenance": "settings",
    "rassylka": "broadcast", "notifyadmins": "broadcast", "broadcast_preview": "broadcast",
    "export": "export", "exportdata": "export", "backup": "export", "csv": "export",
    "ban": "ban", "unban": "ban", "bans": "ban", "antispam_set": "ban",
    "pay": "pay",
    "tickets": "tickets", "ticket": "tickets", "open_tickets": "tickets", "done_tickets": "tickets",
    "findticket": "tickets", "ticketmsg": "tickets", "setstatus": "tickets", "who": "tickets",
    "say": "tickets",
    "note": "notes", "notes": "notes", "delnote": "notes", "clearstate": "notes",
    "reviews": "reviews", "reviews_pending": "reviews",
    "users": "users", "lastusers": "users", "segments": "users", "refstats": "users",
    "stats": "stats", "stats7": "stats", "week": "stats", "healthcheck": "stats", "db": "stats",
    "ping": "stats", "version": "stats", "chatinfo": "stats", "reminders": "stats",
    "panel": "panel", "panelcode": "panel", "panel_code": "panel", "guides": "panel", "guide": "panel",
    "guides_all": "panel",
}


def denied_cmd(chat_id, text):
    cmd = text.split()[0].lstrip("/").split("@")[0]
    need = CMD_PERMS.get(cmd)
    if not need:
        return False
    return not can(chat_id, need)


if os.environ.get("REMINDERS", "1") == "1":
    try:
        threading.Thread(target=reminders_loop, daemon=True).start()
    except Exception as _e:
        print("reminders start error:", _e)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    if POLLING:
        threading.Thread(target=polling, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
