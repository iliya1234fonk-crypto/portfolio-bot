# Бот-портфолио

Телеграм-бот с твоими услугами, ценами, примерами и приёмом заявок.
Заявка приходит тебе в личку.

## Что внутри

- `app.py` — весь бот
- `requirements.txt` — зависимости
- `render.yaml` — готовый конфиг для бесплатного Render
- Приём заявок в 3 шага: занятие → задача → контакт

## Шаг 1. Создать бота в Telegram

1. Открой @BotFather
2. `/newbot`
3. Имя: `Портфолио [твоё имя]`
4. Username: что-то вроде `ivan_dev_bot` (должен заканчиваться на `bot`)
5. Скопируй токен вида `1234567890:AAH...`

## Шаг 2. Узнать свой chat_id

1. Напиши своему боту `/start`
2. Напиши `/id`
3. Он ответит числом — это твой chat_id. Сохрани.

(После деплоя это тоже работает.)

## Шаг 3. Проверить на телефоне (без хостинга)

В Alpine:

```sh
cd /storage/emulated/0/portfolio-bot
pip3 install --break-system-packages -r requirements.txt
BOT_TOKEN="твой_токен" ADMIN_ID="твой_id" POLLING=1 python3 app.py
```

Открой бота в телеграме, нажми /start — меню должно появиться.
Остановить: Ctrl+C или закрыть сессию.

## Шаг 4. Выложить на GitHub

1. Зарегистрируйся на github.com
2. New repository → имя `portfolio-bot` → Public → Create
3. На телефоне:

```sh
cd /storage/emulated/0/portfolio-bot
git init
git add .
git commit -m "portfolio bot"
git branch -M main
git remote add origin https://github.com/ТВОЙ_НИК/portfolio-bot.git
git push -u origin main
```

GitHub попросит логин и токен. Пароль от аккаунта не подойдёт — нужен
Personal Access Token: Settings → Developer settings → Tokens (classic) → Generate new token → галочка `repo`.

## Шаг 5. Задеплоить на Render (бесплатно, без карты)

1. render.com → Sign up через GitHub
2. New → Web Service → выбери репозиторий `portfolio-bot`
3. Language: Python 3
4. Build: `pip install -r requirements.txt`
5. Start: `gunicorn app:app`
6. Plan: Free
7. Environment Variables:
   - `BOT_TOKEN` = токен из шага 1
   - `ADMIN_ID` = твой chat_id
   - `OWNER_USERNAME` = твой ник в телеграме без @
   - `WEBHOOK_SECRET` = любое слово, например `porthub`
8. Create Web Service и жди 2–5 минут

## Шаг 6. Подключить бота к хостингу

Открой в браузере:

```
https://ТВОЙ-АДРЕС.onrender.com/setwebhook?url=https://ТВОЙ-АДРЕС.onrender.com/webhook
```

В ответ должно прийти `{"ok":true, ...}`.

Проверка: напиши боту /start — меню работает.

## Шаг 7. Чтобы не засыпал

Бесплатный Render засыпает через 15 минут простоя, и первый ответ
приходит медленно.

1. Зарегистрируйся на uptimerobot.com (бесплатно)
2. Add New Monitor → HTTP(s)
3. URL: `https://ТВОЙ-АДРЕС.onrender.com/health`
4. Interval: 5 минут

Всё, бот живой круглосуточно.

## Что поменять под себя

В `app.py`:

- `SERVICES` — список услуг и цены
- `EXAMPLES` — примеры. Замени на реальные, когда сделаешь первые демо
- `HELLO` — приветствие
- `OWNER_USERNAME` — твой ник, лучше через переменную окружения

## Как принимать заявки

Каждая заявка приходит тебе в личку от бота: имя, занятие, задача,
контакт и @username. Отвечай сразу — скорость и есть твоё преимущество.
