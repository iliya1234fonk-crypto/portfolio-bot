# -*- coding: utf-8 -*-
"""Режим «Управление аккаунтом» через Telegram Business / Chat automation.

Подключение (делает владелец аккаунта, без Premium):
  1) @BotFather -> /mybots -> Bot Settings -> Business Mode -> включить
  2) Telegram: Настройки -> Автоматизация чатов -> выбрать этого бота
  3) Выбрать чаты и включить «Ответы на сообщения»

Бот получает апдейты business_connection / business_message и может отвечать
от имени аккаунта (с business_connection_id), в пределах выданных прав и
только в чатах, где собеседник писал за последние 24 часа.

Модуль интегрируется в app.py через start() и хуки handle_update/on_admin.
"""

import json
import os
import re
import threading
import time

ENV = {}
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "business.json")
LM = threading.Lock()

DEFAULT_CFG = {
    "enabled": True,
    "hello": "Здравствуйте! Я пока не на связи — оставьте сообщение, отвечу как освобожусь.",
    "away_on": False,
    "away": "Сейчас не на месте. Напишите, что нужно — отвечу позже.",
    "busy_on": False,
    "busy": "Сейчас занят заказом. Отвечу чуть позже, ваше сообщение вижу.",
    "fallback": "",  # пусто = не отвечать, если не сработало правило
    "faq": {},       # "ключевое слово": "ответ"
    "ignore": [],    # chat_id, которым не отвечать
    "notify_admins": True,
    "greet_once": True,  # приветствовать чат только один раз
    "cooldown": 45,      # секунд между автоответами одному чату
}


def _blank():
    return {"connections": {}, "cfg": dict(DEFAULT_CFG), "seen": {}, "last": {},
            "stats": {"in": 0, "out": 0, "leads": 0}, "log": [],
            "games": {}, "mutes": {}}  # games/mutes keyed by "bcid:chat_id"


def _load():
    data = None
    try:
        data = ENV["kv_get"]("business", None)
    except Exception:
        data = None
    if not isinstance(data, dict):
        try:
            with open(FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    if not isinstance(data, dict):
        return _blank()
    out = _blank()
    if isinstance(data.get("connections"), dict):
        out["connections"] = data["connections"]
    if isinstance(data.get("cfg"), dict):
        cfg = dict(DEFAULT_CFG)
        cfg.update({k: v for k, v in data["cfg"].items() if k in DEFAULT_CFG})
        out["cfg"] = cfg
    if isinstance(data.get("seen"), dict):
        out["seen"] = data["seen"]
    if isinstance(data.get("last"), dict):
        out["last"] = data["last"]
    if isinstance(data.get("stats"), dict):
        out["stats"].update({k: int(v) for k, v in data["stats"].items() if k in out["stats"]})
    if isinstance(data.get("log"), list):
        out["log"] = data["log"][-120:]
    if isinstance(data.get("games"), dict):
        out["games"] = data["games"]
    if isinstance(data.get("mutes"), dict):
        out["mutes"] = data["mutes"]
    return out


def _save(m):
    ok = False
    try:
        ok = bool(ENV["kv_set"]("business", m))
    except Exception:
        ok = False
    if not ok:
        try:
            tmp = FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False)
            os.replace(tmp, FILE)
            ok = True
        except Exception as e:
            _log("save", e)
    return ok


def _log(ctx, e):
    try:
        ENV["log"]("biz:" + str(ctx), str(e)[:240])
    except Exception:
        print("biz error", ctx, e)


def _bapi(method, **params):
    return ENV["api"](method, **params)


def _notify(text):
    try:
        for aid in (ENV.get("staff_ids")() if callable(ENV.get("staff_ids")) else []):
            ENV["send"](aid, text)
    except Exception as e:
        _log("notify", e)


def _addlog(m, kind, text):
    m.setdefault("log", []).append({"ts": int(time.time()), "k": str(kind)[:20], "t": str(text)[:220]})
    m["log"] = m["log"][-120:]


def _can_reply(conn):
    rights = (conn or {}).get("rights") or {}
    # Bot API uses can_reply in rights; be permissive if rights missing but connection is on
    return bool(rights.get("can_reply", True))


def _cfg():
    with LM:
        return dict(_load().get("cfg") or DEFAULT_CFG)


def _active_conn(m):
    for cid, c in (m.get("connections") or {}).items():
        if c.get("enabled"):
            return cid, c
    return None, None


# --------------------------------------------------------------- ответы/правила --
def _match_faq(text, faq):
    low = (text or "").lower()
    for key, ans in (faq or {}).items():
        k = str(key).strip().lower()
        if not k:
            continue
        # поддержка нескольких ключей через |
        keys = [x.strip() for x in re.split(r"[|,/]", k) if x.strip()]
        if any(x in low for x in keys):
            return str(ans)
    return None


def _pick_reply(m, conn, chat_id, text):
    cfg = m.get("cfg") or {}
    if not cfg.get("enabled", True):
        return None
    if str(chat_id) in [str(x) for x in (cfg.get("ignore") or [])]:
        return None

    # антиспам: не чаще cooldown на чат
    last = (m.get("last") or {}).get(str(chat_id), 0)
    now = time.time()
    cd = cfg.get("cooldown", 45)
    try:
        cd = int(45 if cd is None else cd)
    except Exception:
        cd = 45
    if cd > 0 and now - float(last or 0) < cd:
        return None

    # приветствие один раз
    seen = m.get("seen") or {}
    if cfg.get("greet_once") and not seen.get(str(chat_id)):
        return cfg.get("hello") or DEFAULT_CFG["hello"]

    if cfg.get("away_on"):
        return cfg.get("away") or DEFAULT_CFG["away"]
    if cfg.get("busy_on"):
        return cfg.get("busy") or DEFAULT_CFG["busy"]

    faq = _match_faq(text, cfg.get("faq") or {})
    if faq:
        return faq

    fb = (cfg.get("fallback") or "").strip()
    return fb or None


# ----------------------------------------------------------- игры / модерация --
ROASTS = [
    "тишина в студии 😶", "молчу-молчу, а тебя не слышу", "сообщение ушло в космос",
    "микрофон выключен, талант тоже", "я это не читал и вам не советую 😶",
    "попробуй ещё раз... хотя нет", "звук пропал, какая жалость",
    "сообщение съел цифровой хомяк", "режим библиотеки: ш-ш-ш",
]


def _bsend(bcid, chat_id, text, keyboard=None):
    p = {"chat_id": chat_id, "text": text, "business_connection_id": bcid}
    if keyboard:
        p["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    return _bapi("sendMessage", **p)


def _bdel(bcid, chat_id, message_id):
    try:
        return _bapi("deleteMessage", chat_id=chat_id, message_id=message_id, business_connection_id=bcid)
    except Exception:
        try:
            return _bapi("deleteMessage", chat_id=chat_id, message_id=message_id)
        except Exception as e:
            _log("del", e)
            return {"ok": False}


def _gkey(bcid, chat_id):
    return "%s:%s" % (bcid, chat_id)


def _mask_word(word):
    return " ".join("•" for _ in word)


def _handle_owner_dot(bcid, conn, chat, sender, msg, text):
    """Команды владельца (.word, .mute, .unmute) в чатах аккаунта."""
    chat_id = chat.get("id")
    mid = msg.get("message_id")
    low = text.strip()
    parts = low.split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == ".word":
        if not arg:
            _bdel(bcid, chat_id, mid)
            _bsend(bcid, chat_id, "Формат: <code>.word твоё_слово</code> (сообщение с командой удалится)")
            return True
        word = arg.split()[0]
        with LM:
            m = _load()
            m.setdefault("games", {})[_gkey(bcid, chat_id)] = {
                "word": word.lower(), "show": word, "by": sender.get("id"), "ts": int(time.time()),
            }
            _save(m)
        _bdel(bcid, chat_id, mid)
        _bsend(bcid, chat_id, "🎯 <b>Игра: угадай слово</b>\n\nБукв: %d\n<code>%s</code>\n\nПиши варианты одним сообщением." % (
            len(word), _mask_word(word)))
        return True

    if cmd == ".wordoff":
        with LM:
            m = _load(); m.setdefault("games", {}).pop(_gkey(bcid, chat_id), None); _save(m)
        _bdel(bcid, chat_id, mid)
        _bsend(bcid, chat_id, "Игра остановлена.")
        return True

    if cmd == ".mute":
        with LM:
            m = _load()
            m.setdefault("mutes", {})[_gkey(bcid, chat_id)] = {"by": sender.get("id"), "ts": int(time.time())}
            _save(m)
        _bdel(bcid, chat_id, mid)
        kb = [[{"text": "Размутить", "callback_data": "bizunmute:%s:%s" % (bcid, chat_id)}]]
        _bsend(bcid, chat_id, "молчи 😶", keyboard=kb)
        return True

    if cmd in (".unmute", ".unmut"):
        with LM:
            m = _load(); m.setdefault("mutes", {}).pop(_gkey(bcid, chat_id), None); _save(m)
        _bdel(bcid, chat_id, mid)
        _bsend(bcid, chat_id, "Ладно, говори 🙂")
        return True

    return False


def _handle_chat_fun(bcid, conn, chat, sender, msg, text):
    """Реакции на сообщения других: угадывание слова, мут."""
    chat_id = chat.get("id")
    mid = msg.get("message_id")
    key = _gkey(bcid, chat_id)
    low = (text or "").strip().lower()

    # игра
    with LM:
        m = _load()
        game = (m.get("games") or {}).get(key)
    if game and low and not low.startswith("."):
        if low == game.get("word") or low == str(game.get("show", "")).lower():
            name = (sender.get("first_name") or "Кто-то")
            with LM:
                m = _load(); m.setdefault("games", {}).pop(key, None); _save(m)
            _bsend(bcid, chat_id, "🎉 %s угадал(а)! Слово: <b>%s</b>" % (name, game.get("show", game.get("word"))))
            return True
        # неверная попытка — не даём автоответу вклиниться
        _bsend(bcid, chat_id, "Не то 🙃 (%d букв: <code>%s</code>)" % (len(game.get("show", "")), _mask_word(game.get("show", ""))))
        return True

    # мут
    with LM:
        m = _load()
        muted = key in (m.get("mutes") or {})
    if muted:
        _bdel(bcid, chat_id, mid)
        import random
        roast = random.choice(ROASTS)
        _bsend(bcid, chat_id, roast)
        return True
    return False


# --------------------------------------------------------------- апдейты --
def handle_business_connection(upd):
    bc = upd.get("business_connection") or {}
    cid = bc.get("id")
    if not cid:
        return False
    with LM:
        m = _load()
        user = bc.get("user") or {}
        m.setdefault("connections", {})[cid] = {
            "id": cid,
            "user_chat_id": bc.get("user_chat_id"),
            "user": {"id": user.get("id"), "name": (user.get("first_name") or "") + ((" " + user.get("last_name")) if user.get("last_name") else ""), "username": user.get("username")},
            "enabled": bool(bc.get("is_enabled", True)),
            "rights": bc.get("rights") or {},
            "date": bc.get("date"),
            "updated": int(time.time()),
        }
        _addlog(m, "conn", ("подключён" if bc.get("is_enabled", True) else "отключён") + " · " + str(user.get("username") or user.get("id") or ""))
        _save(m)
    _notify("<b>Автоматизация чатов</b>\n\nБот %s для аккаунта @%s.\nПрава ответа: %s\n\nНастройка: /biz" % (
        "подключён" if bc.get("is_enabled", True) else "отключён",
        (bc.get("user") or {}).get("username") or "-",
        "да" if _can_reply(bc) else "нет"))
    return True


def handle_business_message(upd):
    is_edit = "edited_business_message" in upd
    msg = upd.get("business_message") or upd.get("edited_business_message")
    if not msg:
        return False
    bcid = msg.get("business_connection_id")
    if not bcid:
        return False
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    sender = msg.get("from") or {}
    text = (msg.get("text") or msg.get("caption") or "").strip()

    if sender.get("is_bot"):
        return True

    with LM:
        m = _load()
        conn = (m.get("connections") or {}).get(bcid) or {}
        if not conn.get("enabled", True):
            return True

    owner_chat = conn.get("user_chat_id")
    owner_id = ((conn.get("user") or {}).get("id"))
    is_owner = (owner_id and str(sender.get("id")) == str(owner_id)) or (owner_chat and str(chat_id) == str(owner_chat))

    # команды владельца (.word .mute .unmute) — работаем и в ЛС
    if is_owner and text.startswith(".") and not is_edit:
        if _handle_owner_dot(bcid, conn, chat, sender, msg, text):
            return True
        return True

    # владелец пишет сам — не автоотвечаем, но команды обработали выше
    if is_owner:
        return True

    # игры/мут для сообщений других
    if not is_edit:
        try:
            if _handle_chat_fun(bcid, conn, chat, sender, msg, text):
                return True
        except Exception as e:
            _log("fun", e)

    name = (sender.get("first_name") or "") + ((" " + sender.get("last_name")) if sender.get("last_name") else "")
    uname = sender.get("username")
    with LM:
        m = _load()
        conn = (m.get("connections") or {}).get(bcid) or {}
        m["stats"]["in"] = int(m["stats"].get("in", 0)) + 1
        _addlog(m, "in", "%s @%s: %s" % (name or chat_id, uname or "-", (text or "[медиа]")[:120]))

        reply = _pick_reply(m, conn, chat_id, text)
        if reply and _can_reply(conn):
            m.setdefault("seen", {})[str(chat_id)] = int(time.time())
            m.setdefault("last", {})[str(chat_id)] = time.time()
            m["stats"]["out"] = int(m["stats"].get("out", 0)) + 1
            _addlog(m, "out", "-> %s: %s" % (chat_id, reply[:120]))
            _save(m)
            res = _bapi("sendMessage", chat_id=chat_id, text=reply, business_connection_id=bcid)
            if not res.get("ok"):
                _log("reply", res)
        else:
            _save(m)

        if (m.get("cfg") or {}).get("notify_admins", True) and text:
            if not (m.get("seen") or {}).get(str(chat_id)) or reply is None:
                _notify("<b>Сообщение (аккаунт)</b>\n\n%s (@%s)\n<code>%s</code>\n\n%s" % (
                    name or "-", uname or "-", chat_id, text[:700]))
                m["stats"]["leads"] = int(m["stats"].get("leads", 0)) + 1
                _save(m)
    return True


# --------------------------------------------------------------- админ-команды --
HELP = (
    "<b>Управление аккаунтом</b> (Chat automation)\n\n"
    "/biz — статус и подключение\n"
    "/biz_on · /biz_off — автоответы вкл/выкл\n"
    "/biz_hello текст — приветствие (первый ответ чату)\n"
    "/biz_away on|off [текст] — режим «нет на месте»\n"
    "/biz_busy on|off [текст] — режим «занят»\n"
    "/biz_fallback текст — ответ, если правило не нашлось (пусто = молчать)\n"
    "/biz_faq — список FAQ\n"
    "/biz_faq add ключ = ответ — добавить (ключи через |)\n"
    "/biz_faq del ключ — удалить\n"
    "/biz_ignore ID — не отвечать чату\n"
    "/biz_unignore ID — снять игнор\n"
    "/biz_notify on|off — уведомлять админов о сообщениях\n"
    "/biz_stats — статистика\n"
    "/biz_log — журнал\n\n"
    "<b>Команды в подключённых чатах (пишешь ты):</b>\n"
    "<code>.word слово</code> — загадай слово (команда удалится, друг угадывает)\n"
    "<code>.wordoff</code> — остановить игру\n"
    "<code>.mute</code> — «молчи 😶» + кнопка размутить, сообщения собеседника удаляются\n"
    "<code>.unmute</code> — размутить\n\n"
    "Подключить: @BotFather → Bot Settings → <b>Business Mode</b> → вкл,\n"
    "затем в Telegram: Настройки → Автоматизация чатов → выбрать бота."
)


def handle_admin(text, chat_id, user):
    t = (text or "").strip()
    cmd = t.split()[0].lower().split("@")[0] if t else ""
    rest = t[len(t.split()[0]):].strip() if t else ""

    if cmd not in ("/biz", "/biz_on", "/biz_off", "/biz_hello", "/biz_away", "/biz_busy",
                   "/biz_fallback", "/biz_faq", "/biz_ignore", "/biz_unignore",
                   "/biz_notify", "/biz_stats", "/biz_log", "/biz_help"):
        return False
    if not (ENV.get("is_admin") and ENV["is_admin"](chat_id)):
        ENV["send"](chat_id, "Только для админов.")
        return True

    if cmd in ("/biz", "/biz_help"):
        with LM:
            m = _load()
        conns = list((m.get("connections") or {}).values())
        cfg = m.get("cfg") or {}
        lines = [HELP, ""]
        if conns:
            for c in conns[-3:]:
                u = c.get("user") or {}
                lines.append("Подключение: @%s · %s · ответ %s" % (
                    u.get("username") or u.get("id") or "-", "вкл" if c.get("enabled") else "выкл",
                    "да" if _can_reply(c) else "нет"))
        else:
            lines.append("Подключений пока нет — подключи бота в «Автоматизация чатов».")
        lines.append("\nРежим: %s · away %s · busy %s · FAQ %s" % (
            "вкл" if cfg.get("enabled") else "выкл", "вкл" if cfg.get("away_on") else "выкл",
            "вкл" if cfg.get("busy_on") else "выкл", len(cfg.get("faq") or {})))
        ENV["send"](chat_id, "\n".join(lines))
        return True

    with LM:
        m = _load()
        cfg = m.setdefault("cfg", dict(DEFAULT_CFG))

        if cmd == "/biz_on":
            cfg["enabled"] = True; _save(m); ENV["send"](chat_id, "Автоответы аккаунта: <b>включены</b>.")
        elif cmd == "/biz_off":
            cfg["enabled"] = False; _save(m); ENV["send"](chat_id, "Автоответы аккаунта: <b>выключены</b>.")
        elif cmd == "/biz_hello":
            if not rest:
                ENV["send"](chat_id, "Сейчас: %s\n\nЗадать: <code>/biz_hello текст</code>" % (cfg.get("hello") or "—"))
            else:
                cfg["hello"] = rest; _save(m); ENV["send"](chat_id, "Приветствие обновлено.")
        elif cmd == "/biz_away":
            parts = rest.split(None, 1)
            if parts and parts[0].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
                cfg["away_on"] = parts[0].lower() in ("on", "вкл", "1")
                if len(parts) > 1:
                    cfg["away"] = parts[1]
                _save(m)
            elif rest:
                cfg["away"] = rest; cfg["away_on"] = True; _save(m)
            ENV["send"](chat_id, "Away: <b>%s</b>\n%s" % ("вкл" if cfg.get("away_on") else "выкл", cfg.get("away") or ""))
        elif cmd == "/biz_busy":
            parts = rest.split(None, 1)
            if parts and parts[0].lower() in ("on", "off", "вкл", "выкл", "1", "0"):
                cfg["busy_on"] = parts[0].lower() in ("on", "вкл", "1")
                if len(parts) > 1:
                    cfg["busy"] = parts[1]
                _save(m)
            elif rest:
                cfg["busy"] = rest; cfg["busy_on"] = True; _save(m)
            ENV["send"](chat_id, "Busy: <b>%s</b>\n%s" % ("вкл" if cfg.get("busy_on") else "выкл", cfg.get("busy") or ""))
        elif cmd == "/biz_fallback":
            cfg["fallback"] = rest; _save(m)
            ENV["send"](chat_id, "Fallback: %s" % ("выключен (молчу)" if not rest else rest[:400]))
        elif cmd == "/biz_faq":
            if rest.startswith("add "):
                body = rest[4:].strip()
                if "=" not in body:
                    ENV["send"](chat_id, "Формат: <code>/biz_faq add цена|прайс = Наши цены: ...</code>")
                else:
                    k, v = body.split("=", 1)
                    cfg.setdefault("faq", {})[k.strip()] = v.strip()
                    _save(m); ENV["send"](chat_id, "FAQ добавлен: <b>%s</b>" % k.strip())
            elif rest.startswith("del "):
                k = rest[4:].strip().lower()
                faq = cfg.get("faq") or {}
                hit = next((x for x in faq if x.lower() == k), None)
                if hit:
                    faq.pop(hit, None); _save(m); ENV["send"](chat_id, "FAQ удалён: %s" % hit)
                else:
                    ENV["send"](chat_id, "Не нашёл ключ: %s" % k)
            else:
                faq = cfg.get("faq") or {}
                if not faq:
                    ENV["send"](chat_id, "FAQ пуст. Добавить: <code>/biz_faq add цена|стоимость = ...</code>")
                else:
                    lines = ["<b>FAQ аккаунта</b>", ""]
                    for k, v in list(faq.items())[:30]:
                        lines.append("• <b>%s</b>\n  %s" % (k, str(v)[:140]))
                    ENV["send"](chat_id, "\n".join(lines))
        elif cmd == "/biz_ignore":
            if rest:
                cfg.setdefault("ignore", [])
                if rest not in cfg["ignore"]:
                    cfg["ignore"].append(rest)
                _save(m); ENV["send"](chat_id, "Игнор: %s" % rest)
            else:
                ENV["send"](chat_id, "Игнор-лист: %s" % (", ".join(cfg.get("ignore") or []) or "пуст"))
        elif cmd == "/biz_unignore":
            cfg["ignore"] = [x for x in (cfg.get("ignore") or []) if x != rest]
            _save(m); ENV["send"](chat_id, "Убран из игнора: %s" % rest)
        elif cmd == "/biz_notify":
            cfg["notify_admins"] = rest.lower() in ("on", "вкл", "1", "yes", "да") if rest else not cfg.get("notify_admins", True)
            _save(m); ENV["send"](chat_id, "Уведомления админам: <b>%s</b>" % ("вкл" if cfg.get("notify_admins") else "выкл"))
        elif cmd == "/biz_stats":
            st = m.get("stats") or {}
            ENV["send"](chat_id, "<b>Статистика аккаунта</b>\n\nВходящих: %s\nАвтоответов: %s\nЛидов: %s\nПодключений: %s\nFAQ: %s" % (
                st.get("in", 0), st.get("out", 0), st.get("leads", 0), len(m.get("connections") or {}), len((cfg.get("faq") or {}))))
        elif cmd == "/biz_log":
            rows = list(reversed((m.get("log") or [])[-15:]))
            if not rows:
                ENV["send"](chat_id, "Журнал пуст.")
            else:
                lines = ["<b>Журнал аккаунта</b>", ""]
                for r in rows:
                    lines.append("%s · %s · %s" % (time.strftime("%d.%m %H:%M", time.localtime(r.get("ts", 0))), r.get("k"), r.get("t")))
                ENV["send"](chat_id, "\n".join(lines))
    return True


# --------------------------------------------------------------- интеграция --
def handle_callback(cb):
    data = (cb.get("data") or "")
    if not data.startswith("bizunmute:"):
        return False
    # bizunmute:bcid:chat_id
    parts = data.split(":", 2)
    if len(parts) != 3:
        _bapi("answerCallbackQuery", callback_query_id=cb.get("id"), text="Ошибка")
        return True
    _, bcid, chat_id = parts
    with LM:
        m = _load(); m.setdefault("mutes", {}).pop(_gkey(bcid, chat_id), None); _save(m)
    _bapi("answerCallbackQuery", callback_query_id=cb.get("id"), text="Размучено")
    # обновим сообщение, если можем
    msg = cb.get("message") or {}
    try:
        _bapi("editMessageText", chat_id=msg.get("chat", {}).get("id"), message_id=msg.get("message_id"),
              text="Ладно, говори 🙂", business_connection_id=bcid)
    except Exception:
        try:
            _bapi("editMessageText", chat_id=msg.get("chat", {}).get("id"), message_id=msg.get("message_id"),
                  text="Ладно, говори 🙂")
        except Exception:
            _bsend(bcid, chat_id, "Ладно, говори 🙂")
    return True


def handle_update(update):
    if "business_connection" in update:
        return handle_business_connection(update)
    if "business_message" in update or "edited_business_message" in update:
        return handle_business_message(update)
    if "deleted_business_messages" in update:
        return True
    if "callback_query" in update and (update["callback_query"].get("data") or "").startswith("bizunmute:"):
        return handle_callback(update["callback_query"])
    return False


def start(env):
    ENV.update(env)
    return True
