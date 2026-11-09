# -*- coding: utf-8 -*-
"""Режим «Календарь» для portfolio-bot.

Админ включает режим командой /calendar, пишет задачи обычным текстом:

    завтра 15:00 написать Мише насчёт сайта
    через 2 часа позвонить клиенту
    12.11 09:30 отправить счёт
    в понедельник 10:00 созвон
    каждый понедельник 10:00 созвон            — повторяется каждую неделю
    каждый день 09:00 проверить заявки          — повторяется каждый день
    всем админам завтра 10:00 созвон            — придёт всем админам
    завтра 15:00 написать по заявке 123         — привязка к заявке

Команды: /calendar /calendar_off /cal_list /cal_week /cal_del [id] /cal_done [id] /cal_tz 5

Модуль самостоятельный: app.py передаёт функции через start().
"""

import json
import os
import re
import threading
import time
import datetime as dt

ENV = {}
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar.json")
TICK = 15
LM = threading.Lock()

WD = {
    "пн": 0, "понедельник": 0,
    "вт": 1, "вторник": 1,
    "ср": 2, "среда": 2, "среду": 2,
    "чт": 3, "четверг": 3,
    "пт": 4, "пятница": 4, "пятницу": 4,
    "сб": 5, "суббота": 5, "субботу": 5,
    "вс": 6, "воскресенье": 6,
}

RE_REL = re.compile(r"через\s+(\d+)\s*(минут\w*|мин|м|час\w*|ч|дн\w*|день|дня|дней|недел\w*)", re.I)
RE_TIME = re.compile(r"(?:^|\s)(?:в\s*)?(\d{1,2})[:.](\d{2})(?!\d)")
RE_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?")
RE_DAY = re.compile(r"(сегодня|завтра|послезавтра|в\s+(пн|вт|ср|чт|пт|сб|вс|понедельник|вторник|среду|среда|четверг|пятницу|пятница|субботу|суббота|воскресенье))", re.I)
RE_EVERY = re.compile(r"^(?:кажд(?:ый|ую|ое)\s+)(день|пн|вт|ср|чт|пт|сб|вс|понедельник|вторник|среду|среда|четверг|пятницу|пятница|субботу|суббота|воскресенье)\b", re.I)
RE_ALL = re.compile(r"^(?:всем\s+админ(?:ам|ам\s+бота)|для\s+всех\s+админ\w*)[\s,.:—-]*", re.I)
RE_TICKET = re.compile(r"(?:по\s+заявк[еи]\s*#?|заявк[аи]\s*#?|тикет\w*\s*#?|#)(\d{1,8})\b", re.I)
RE_CLIENT = re.compile(r"(?:клиент[ау]?\s*|чату?\s*|пользовател[юя]?\s*)(\d{6,15})\b", re.I)


# ------------------------------------------------------------------ хранилище --
def _blank():
    return {"on": {}, "tasks": [], "seq": 0, "tz": 5}


def _norm(d):
    out = _blank()
    if isinstance(d, dict):
        if isinstance(d.get("on"), dict):
            out["on"] = {str(k): bool(v) for k, v in d["on"].items()}
        if isinstance(d.get("tasks"), list):
            out["tasks"] = [t for t in d["tasks"] if isinstance(t, dict) and t.get("at")]
        try:
            out["seq"] = int(d.get("seq") or 0)
        except Exception:
            out["seq"] = 0
        try:
            out["tz"] = int(d.get("tz", 5))
        except Exception:
            out["tz"] = 5
    return out


def _load():
    data = None
    try:
        data = ENV["kv_get"]("calendar", None)
    except Exception:
        data = None
    if not isinstance(data, dict):
        try:
            with open(FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    return _norm(data)


def _save(m):
    ok = False
    try:
        ok = bool(ENV["kv_set"]("calendar", m))
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


# ------------------------------------------------------------------- утилиты --
def _log(ctx, e):
    try:
        ENV["log"]("calendar:" + str(ctx), str(e)[:200])
    except Exception:
        print("calendar error", ctx, e)


def _send(chat_id, text, keyboard=None):
    try:
        ENV["send"](chat_id, text, keyboard)
    except Exception as e:
        _log("send", e)


def _staff():
    try:
        v = ENV.get("staff_ids")
        ids = v() if callable(v) else v
        return [str(x) for x in (ids or [])]
    except Exception:
        return []


def _tz(m):
    return dt.timezone(dt.timedelta(hours=int(m.get("tz", 5))))


def _now(m):
    return dt.datetime.now(dt.timezone.utc).astimezone(_tz(m))


def _fmt(ts, m):
    return dt.datetime.fromtimestamp(float(ts), _tz(m)).strftime("%d.%m %H:%M")


def _label(ts, m):
    now = _now(m)
    d = dt.datetime.fromtimestamp(float(ts), now.tzinfo)
    days = (d.date() - now.date()).days
    if days < 3:
        return "%s %s" % (_when_word(ts, now), d.strftime("%H:%M"))
    return d.strftime("%d.%m %H:%M")


def _when_word(ts, now):
    d = dt.datetime.fromtimestamp(float(ts), now.tzinfo)
    days = (d.date() - now.date()).days
    if days == 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    if days == 2:
        return "послезавтра"
    return d.strftime("%d.%m")


def _targets(task):
    if task.get("to") == "all_admins":
        ids = _staff()
        return ids or [str(task.get("chat"))]
    return [str(task.get("chat"))]


def _task_can(task, chat_id):
    if str(task.get("chat")) == str(chat_id):
        return True
    if task.get("to") == "all_admins" and str(chat_id) in _staff():
        return True
    return False


def _repeat_label(rep):
    if not rep:
        return ""
    if rep.get("type") == "daily":
        return " · каждый день"
    if rep.get("type") == "weekly":
        names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        return " · кажд. %s" % names[int(rep.get("wd", 0)) % 7]
    return ""


def _attach(task):
    bits = []
    if task.get("to") == "all_admins":
        bits.append("всем админам")
    if task.get("ticket"):
        bits.append("заявка #%s" % task["ticket"])
    if task.get("client"):
        bits.append("клиент %s" % task["client"])
    return (" [%s]" % ", ".join(bits)) if bits else ""


def _next_repeat(rep, ts, tz):
    d = dt.datetime.fromtimestamp(float(ts), tz)
    if rep.get("type") == "daily":
        nxt = d + dt.timedelta(days=1)
    elif rep.get("type") == "weekly":
        wd = int(rep.get("wd", d.weekday())) % 7
        diff = (wd - d.weekday()) % 7 or 7
        nxt = d + dt.timedelta(days=diff)
    else:
        return None
    return nxt.timestamp()


# --------------------------------------------------------------- разбор текста --
def _parse_meta(src):
    body = src
    meta = {"repeat": None, "to": None, "ticket": None, "client": None}

    m = RE_ALL.match(body)
    if m:
        meta["to"] = "all_admins"
        body = body[m.end():].strip()

    m = RE_EVERY.match(body)
    if m:
        word = m.group(1).lower()
        if word == "день":
            meta["repeat"] = {"type": "daily"}
        else:
            meta["repeat"] = {"type": "weekly", "wd": WD.get(word, 0)}
        body = body[m.end():].strip()

    m = RE_TICKET.search(body)
    if m:
        meta["ticket"] = m.group(1)
        # не вырезаем — пусть остаётся в тексте как контекст
    m = RE_CLIENT.search(body)
    if m:
        meta["client"] = m.group(1)

    return body, meta


def parse(text, now):
    """Вернуть (ts, body, meta) либо (None, reason, None)."""
    src = (text or "").strip()
    src, meta = _parse_meta(src)
    low = src.lower()
    body = src
    when = None
    mode = None

    m = RE_REL.search(low)
    if m:
        mode = "rel"
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith(("мин", "м")):
            delta = dt.timedelta(minutes=n)
        elif unit.startswith(("час", "ч")):
            delta = dt.timedelta(hours=n)
        elif unit.startswith("недел"):
            delta = dt.timedelta(weeks=n)
        else:
            delta = dt.timedelta(days=n)
        when = now + delta
        body = src[:m.start()] + src[m.end():]

    if when is None:
        m = RE_DATE.search(low)
        if m:
            mode = "date"
            day, mon = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else now.year
            if year < 100:
                year += 2000
            try:
                when = now.replace(year=year, month=mon, day=day)
            except ValueError:
                return None, "Такой даты нет.", None
            body = src[:m.start()] + src[m.end():]

    day_shift = None
    if when is None:
        m = RE_DAY.search(low)
        if m:
            mode = "day"
            word = m.group(1).lower().replace(" ", "")
            if word == "сегодня":
                day_shift = 0
            elif word == "завтра":
                day_shift = 1
            elif word == "послезавтра":
                day_shift = 2
            else:
                key = word.lstrip("в")
                wd = WD.get(key)
                if wd is not None:
                    diff = (wd - now.weekday()) % 7
                    day_shift = 7 if diff == 0 else diff
            body = src[:m.start()] + src[m.end():]

    m = RE_TIME.search(body)
    hour = minute = None
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        body = body[:m.start()] + " " + body[m.end():]
        if hour > 23 or minute > 59:
            return None, "Время должно быть вида 15:30.", None

    if when is None:
        if hour is None:
            if meta["repeat"]:
                return None, "Для повтора укажи время: <code>каждый понедельник 10:00 созвон</code>", None
            return None, "Не понял время. Примеры:\n<code>завтра 15:00 написать Мише</code>\n<code>через 2 часа позвонить</code>\n<code>каждый понедельник 10:00 созвон</code>\n<code>всем админам завтра 10:00 созвон</code>", None
        base = now + dt.timedelta(days=day_shift or 0)
        when = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if mode is None and meta.get("repeat", {}).get("type") == "weekly" and (day_shift or 0) == 0:
            wd = int(meta["repeat"].get("wd", now.weekday())) % 7
            diff = (wd - now.weekday()) % 7
            cand = (now + dt.timedelta(days=diff)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if cand <= now:
                cand += dt.timedelta(days=7)
            when = cand
        elif when <= now and (day_shift or 0) == 0:
            when += dt.timedelta(days=1)
    elif mode == "rel":
        pass
    elif hour is not None:
        when = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
    else:
        when = when.replace(hour=9, minute=0, second=0, microsecond=0)

    if when <= now and not meta["repeat"]:
        return None, "Это время уже прошло — укажи будущее.", None
    if when <= now and meta["repeat"]:
        nxt = _next_repeat(meta["repeat"], when.timestamp(), now.tzinfo)
        if nxt:
            when = dt.datetime.fromtimestamp(nxt, now.tzinfo)

    clean = re.sub(r"^(напомни(?:ть)?|напоминание|задача)\s*[:,]?\s*", "", body.strip(), flags=re.I)
    clean = re.sub(r"\s{2,}", " ", clean).strip(" ,-—")
    if not clean:
        clean = "Напоминание"
    return when.timestamp(), clean, meta


# ------------------------------------------------------------------ вывод списка --
def _visible(m, chat_id):
    me = str(chat_id)
    staff = set(_staff())
    return [t for t in m["tasks"] if not t.get("done") and (
        str(t.get("chat")) == me or (t.get("to") == "all_admins" and me in staff)
    )]


def _list_text(m, chat_id, week=False):
    tasks = _visible(m, chat_id)
    tasks.sort(key=lambda t: float(t["at"]))
    on = bool(m["on"].get(str(chat_id)))
    if week:
        now = _now(m)
        end = now + dt.timedelta(days=7)
        tasks = [t for t in tasks if dt.datetime.fromtimestamp(float(t["at"]), now.tzinfo) <= end]
        head = "<b>Календарь — неделя</b>\n"
    else:
        head = "<b>Календарь</b> — режим %s\n" % ("включён" if on else "выключен")
    if not tasks:
        tail = "На неделю задач нет." if week else "\nЗадач нет. Примеры:\n<code>завтра 15:00 написать Мише</code>\n<code>каждый понедельник 10:00 созвон</code>\n<code>всем админам завтра 10:00 созвон</code>"
        return head + ("\n" if week else "") + tail
    lines = []
    for t in tasks[:40]:
        lines.append("• <code>%s</code> #%s — %s%s%s" % (
            _label(t["at"], m), t.get("id"), t.get("text", ""),
            _repeat_label(t.get("repeat")), _attach(t)))
    tail = "" if on or week else "\n\nВключить: /calendar"
    return head + "\n" + "\n".join(lines) + tail


def _kb(m, chat_id):
    tasks = _visible(m, chat_id)
    if not tasks:
        return None
    return [[{"text": "Неделя", "callback_data": "cal_week"},
             {"text": "Удалить последнюю", "callback_data": "cal_del:last"}],
            [{"text": "Выключить режим", "callback_data": "cal_off"}]]


def _add(m, chat_id, ts, text, meta=None):
    meta = meta or {}
    m["seq"] = int(m.get("seq") or 0) + 1
    m["tasks"].append({
        "id": m["seq"],
        "chat": str(chat_id),
        "to": meta.get("to"),
        "at": float(ts),
        "text": text,
        "repeat": meta.get("repeat"),
        "ticket": meta.get("ticket"),
        "client": meta.get("client"),
        "done": False,
        "sent": False,
        "created": time.time(),
    })
    return m["seq"]


# ---------------------------------------------------------------- входящие сообщения --
def handle(chat_id, text, user):
    """Вернуть True, если сообщение обработано календарём."""
    t = (text or "").strip()
    if not t:
        return False
    cmd = t.split()[0].lower().split("@")[0]
    rest = t[len(t.split()[0]):].strip()

    if cmd in ("/calendar", "/cal"):
        with LM:
            m = _load()
            m["on"][str(chat_id)] = True
            _save(m)
        _send(chat_id, _list_text(m, chat_id), _kb(m, chat_id))
        return True

    if cmd in ("/calendar_off", "/cal_off", "/caloff"):
        with LM:
            m = _load()
            m["on"].pop(str(chat_id), None)
            _save(m)
        _send(chat_id, "<b>Календарь выключен.</b> Бот снова в обычном режиме.", [[{"text": "В меню", "callback_data": "menu"}]])
        return True

    if cmd in ("/cal_list", "/calendar_list"):
        with LM:
            m = _load()
        _send(chat_id, _list_text(m, chat_id), _kb(m, chat_id))
        return True

    if cmd == "/cal_week":
        with LM:
            m = _load()
        _send(chat_id, _list_text(m, chat_id, week=True), _kb(m, chat_id))
        return True

    if cmd == "/cal_tz":
        try:
            tz = int(rest)
            if not -12 <= tz <= 14:
                raise ValueError
        except Exception:
            with LM:
                m = _load()
            _send(chat_id, "Сейчас часовой пояс: UTC%+d. Задать: <code>/cal_tz 5</code>" % int(m.get("tz", 5)))
            return True
        with LM:
            m = _load()
            m["tz"] = tz
            _save(m)
        _send(chat_id, "Часовой пояс: <b>UTC%+d</b>." % tz)
        return True

    if cmd in ("/cal_del", "/cal_done", "/cal_stop"):
        with LM:
            m = _load()
            mine = _visible(m, chat_id)
            mine.sort(key=lambda x: float(x["at"]))
            if not mine:
                _send(chat_id, "Активных задач нет.")
                return True
            if rest in ("", "last"):
                task = mine[-1]
            else:
                task = next((x for x in mine if str(x.get("id")) == rest), None)
            if not task or not _task_can(task, chat_id):
                _send(chat_id, "Не нашёл такую задачу. Список: /cal_list")
                return True
            if cmd == "/cal_done" and task.get("repeat"):
                nxt = _next_repeat(task["repeat"], float(task["at"]), _tz(m))
                task["at"] = nxt or (time.time() + 86400)
                task["sent"] = False
                msg = "Готово (повтор): %s — след. %s" % (task.get("text", ""), _label(task["at"], m))
            elif cmd == "/cal_stop" or (cmd == "/cal_done" and task.get("repeat")):
                # /cal_stop handled above? no - /cal_done+repeat reschedules; /cal_stop removes
                if cmd == "/cal_stop":
                    m["tasks"].remove(task)
                    msg = "Повтор остановлен: %s" % task.get("text", "")
                else:
                    msg = "Готово (повтор): %s — след. %s" % (task.get("text", ""), _label(task["at"], m))
            elif cmd == "/cal_done":
                task["done"] = True
                task["sent"] = True
                msg = "Готово: %s" % task.get("text", "")
            else:
                m["tasks"].remove(task)
                msg = "Удалено: %s" % task.get("text", "")
            _save(m)
        _send(chat_id, msg, _kb(m, chat_id))
        return True

    with LM:
        m = _load()
        if not m["on"].get(str(chat_id)):
            return False
        if t.startswith("/"):
            return False
        ts, body, meta = parse(t, _now(m))
        if ts is None:
            _send(chat_id, body)
            return True
        tid = _add(m, chat_id, ts, body, meta)
        _save(m)

    extra = _repeat_label((meta or {}).get("repeat")) + _attach({"to": (meta or {}).get("to"), "ticket": (meta or {}).get("ticket"), "client": (meta or {}).get("client")})
    _send(chat_id,
          "<b>Записал</b> #%d%s\n%s — %s\n\nСписок: /cal_list · Неделя: /cal_week · Выключить: /calendar_off" % (
              tid, extra, _label(ts, m), body),
          _kb(m, chat_id))
    return True


def on_callback(data, chat_id, user):
    if not data.startswith("cal_"):
        return False
    action, _, arg = data.partition(":")
    action = action[4:]

    if action == "off":
        with LM:
            m = _load()
            m["on"].pop(str(chat_id), None)
            _save(m)
        _send(chat_id, "<b>Календарь выключен.</b>", [[{"text": "В меню", "callback_data": "menu"}]])
        return True

    if action == "week":
        with LM:
            m = _load()
        _send(chat_id, _list_text(m, chat_id, week=True), _kb(m, chat_id))
        return True

    with LM:
        m = _load()
        if arg in ("", "last"):
            live = [x for x in _visible(m, chat_id)]
            live.sort(key=lambda x: float(x["at"]))
            task = live[-1] if live else None
        else:
            task = next((x for x in m["tasks"] if str(x.get("id")) == arg), None)
        if not task or not _task_can(task, chat_id):
            _send(chat_id, "Задача не найдена.")
            return True
        if action == "stop":
            m["tasks"].remove(task)
            msg = "Повтор остановлен: %s" % task.get("text", "")
        elif action == "done":
            if task.get("repeat"):
                nxt = _next_repeat(task["repeat"], float(task["at"]), _tz(m))
                task["at"] = nxt or (time.time() + 86400)
                task["sent"] = False
                msg = "Готово (повтор) — след. %s: %s" % (_label(task["at"], m), task.get("text", ""))
            else:
                task["done"] = True
                task["sent"] = True
                msg = "Отмечено готовым: %s" % task.get("text", "")
        elif action == "snooze":
            task["at"] = time.time() + 15 * 60
            task["sent"] = False
            task["done"] = False
            msg = "Отложено на 15 минут: %s" % task.get("text", "")
        elif action == "del":
            m["tasks"].remove(task)
            msg = "Удалено: %s" % task.get("text", "")
        else:
            return False
        _save(m)
    _send(chat_id, msg, _kb(m, chat_id))
    return True


# --------------------------------------------------------------------- отправка --
def _task_kb(task):
    tid = str(task.get("id"))
    row = [{"text": "Готово", "callback_data": "cal_done:" + tid},
           {"text": "+15 мин", "callback_data": "cal_snooze:" + tid}]
    row2 = [{"text": "Удалить", "callback_data": "cal_del:" + tid}]
    if task.get("repeat"):
        row2.append({"text": "Стоп повтор", "callback_data": "cal_stop:" + tid})
    return [row, row2]


def tick():
    with LM:
        m = _load()
        now = time.time()
        due = [t for t in m["tasks"] if not t.get("done") and not t.get("sent") and float(t["at"]) <= now]
        if not due:
            return
        for t in due:
            if t.get("repeat"):
                # подготовим следующее время, но отправим сейчас; sent вернём в False после успешной отправки? проще: пометим sent и потом пересчитаем в доставке нельзя; сделаем: оставим sent=True временно, а в цикле ниже после отправки перенесём.
                t["_fired_at"] = float(t["at"])
            t["sent"] = True
        _save(m)

    reschedule = []
    for t in due:
        try:
            extra = _repeat_label(t.get("repeat")) + _attach(t)
            text = "<b>Напоминание</b>%s\n%s · %s" % (extra, _fmt(t.get("_fired_at") or t["at"], m), t.get("text", ""))
            for cid in _targets(t):
                _send(int(cid), text, _task_kb(t))
            if t.get("repeat"):
                reschedule.append((t.get("id"), t.get("repeat"), t.get("_fired_at") or t["at"]))
        except Exception as e:
            _log("tick", e)

    if reschedule:
        with LM:
            m = _load()
            tz = _tz(m)
            by_id = {str(x.get("id")): x for x in m["tasks"]}
            for tid, rep, fired in reschedule:
                task = by_id.get(str(tid))
                if not task:
                    continue
                nxt = _next_repeat(rep, float(fired), tz)
                task["at"] = nxt or (time.time() + 86400)
                task["sent"] = False
                task.pop("_fired_at", None)
            _save(m)


def _loop():
    while True:
        try:
            tick()
        except Exception as e:
            _log("loop", e)
        time.sleep(TICK)


def start(env):
    """Передать функции из app.py и запустить фоновую проверку."""
    ENV.update(env)
    if str(ENV.get("_thread", "")) != "on":
        ENV["_thread"] = "on"
        threading.Thread(target=_loop, daemon=True).start()
    return True
