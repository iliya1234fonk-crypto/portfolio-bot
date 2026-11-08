import os
import time
os.environ.setdefault("BOT_TOKEN", "9247836749:AAGRpTU31dt6LL_2uDuC3dA6gTQSoWlreAk")
os.environ.setdefault("ADMIN_ID", "8009841546")
os.environ.setdefault("OWNER_USERNAME", "z0nchik")
import app

app.BOT_USERNAME = "portfoli_robot"
kb = app.broadcast_kb()

# лимит Telegram на загрузку гифок — ждём, пока отпустит
time.sleep(245)

for cid in list(app.USERS.keys()):
    for attempt in range(5):
        r = app.send_animation(cid, app.EXAMPLES_SITES_CAPTION, kb, "examples_sites.gif")
        if r.get("ok"):
            print("sent", cid, flush=True)
            break
        desc = str(r.get("description", ""))
        print("fail", cid, desc, flush=True)
        wait = 60
        if "retry after" in desc:
            try:
                wait = int(desc.split("retry after")[1].strip()) + 5
            except Exception:
                wait = 120
        time.sleep(min(wait, 400))
    time.sleep(5)

print("done", flush=True)
