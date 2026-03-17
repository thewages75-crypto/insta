#USERNAM TO MEDIA INSTA BOT(OG)
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from playwright.sync_api import sync_playwright
import threading
import requests
import datetime
import time
import random
import re
import json
from io import BytesIO
from queue import Queue
import instaloader
# =========================
# BOT TOKEN
# =========================
DEBUG_MESSAGES = {}
TOKEN = "8665521420:AAHi0hfMNn3odVDCd9ajMCW_8FwrSz2OQLQ"
bot = telebot.TeleBot(TOKEN, threaded=True)
from queue import Queue

job_queue = Queue()
DEBUG = True
ADMIN_ID = 8305774350  # put your Telegram ID
# =========================
# INSTAGRAM SESSION
# =========================
control_queue = Queue()
PLAYWRIGHT_CONTEXT = None
IG_SESSIONID = "45575449095%3AUrvTriciDLscrU%3A24%3AAYgshiZX6sRl6C2ExuxUpILUH2MRrq63Vb4I8_mMtw"
CURRENT_SESSION = IG_SESSIONID
WAITING_SESSION = {}
LAST_SESSION_CHECK = 0
SESSION_CHECK_INTERVAL = 300  # 5 minutes

# =========================
# JOB SYSTEM
import os
import sys

def restart_bot():
    log("🔄 Restarting bot process...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

def is_session_valid(sessionid):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
        }

        cookies = {
            "sessionid": sessionid
        }

        r = requests.get(
            "https://www.instagram.com/",
            headers=headers,
            cookies=cookies,
            timeout=10,
            allow_redirects=False  # 🔥 IMPORTANT
        )
        # if redirected to login → invalid
        if r.status_code in [301, 302]:
            return False

        if r.status_code != 200:
            return False

        return True

    except Exception as e:
        log(f"Session check error: {e}")
        return False
# =========================
# LOG FUNCTION
# =========================
def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")
def debug(chat_id, text):

    if not DEBUG or not chat_id:
        return

    try:
        # edit if exists
        if chat_id in DEBUG_MESSAGES:
            bot.edit_message_text(
                text,
                chat_id,
                DEBUG_MESSAGES[chat_id]
            )
            return

        # otherwise send new
        msg = bot.send_message(chat_id, text)
        DEBUG_MESSAGES[chat_id] = msg.message_id

    except Exception as e:
        print(f"Debug error: {e}")
# SESSION FUNCTION
import os
print("Files in project:", os.listdir())
# =========================
# INSTALOADER
# =========================

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False
)

if not is_session_valid(IG_SESSIONID):
    print("❌ Developer session is INVALID")
else:
    print("✅ Developer session is VALID")

L.context._session.cookies.set(
    "sessionid",
    IG_SESSIONID,
    domain=".instagram.com"
)
# =========================
# START PLAYWRIGHT
# =========================
def update_playwright_session(context):
    if context is None:
        log("no context found")
        return

    context.clear_cookies()
    context.add_cookies([{
        "name": "sessionid",
        "value": CURRENT_SESSION,
        "domain": ".instagram.com",
        "path": "/",
        "httpOnly": True,
        "secure": True,
        "sameSite": "None"
    }])
print("Starting browser...")

def get_profile_posts(username, limit=100):

    posts = []

    profile = instaloader.Profile.from_username(
        L.context,
        username
    )

    for post in profile.get_posts():

        posts.append(post)

        if len(posts) >= limit:
            break

    log(f"Collected {len(posts)} posts using Instaloader")

    return posts
def extract_media(post):

    items = []

    # carousel
    if post.typename == "GraphSidecar":

        for node in post.get_sidecar_nodes():

            if node.is_video:
                items.append(("video", node.video_url))
            else:
                items.append(("photo", node.display_url))

    # single video
    elif post.is_video:

        items.append(("video", post.video_url))

    # single image
    else:

        items.append(("photo", post.url))

    return items

def get_post_from_url(post_url):

    try:

        shortcode = re.search(r"(?:p|reel|tv)/([^/?]+)", post_url).group(1)

        post = instaloader.Post.from_shortcode(
            L.context,
            shortcode
        )

        return post

    except Exception as e:

        log(f"Instaloader error: {e}")
        return None
# =========================
# SCRAPER
# =========================

def scrape_background(job, context):
    username = job.username
    log(f"Scraping started for {username}")
    job.status = "opening_page"
    debug(job.chat_id, f"[{job.username}] Opening page")

    

    try:

        page = context.new_page()

        url = f"https://www.instagram.com/{username}/"
        
        delay = random.uniform(4,7)
        time.sleep(delay)

        page.goto(url, wait_until="domcontentloaded")

        time.sleep(5)
        job.status = "loaded_page"
        log(f"Current URL: {page.url}")
        title = page.title()
        log(f"page title : {title}")
        title = page.title()
        try:
            bot.send_message(job.chat_id, f"🌐 Page Title:\n{title}")
            bot.send_message(job.chat_id, f"🔗 Current URL:\n{page.url}")
        except Exception as e:
            log(f"Telegram error: {e}")
        if "challenge" in page.url:
            job.status = "challenge"
            debug(job.chat_id, f"[{job.username}]Instagram triggered a security challenge. Session is blocked.")
            page.close()
            return

        if "accounts/login" in page.url:
            job.status = "session_expired"
            debug(job.chat_id, f"[{job.username}]Session expired. Instagram requires login.")
            page.close()
            return
        # wait until page loads
        page.wait_for_load_state("networkidle")

        # small delay for JS rendering
        time.sleep(3)

        # scroll once to trigger posts loading
        page.evaluate("""
        window.scrollBy({
            top: 800,
            left: 0,
            behavior: 'smooth'
        });
        """)
        time.sleep(random.uniform(4,6))

        max_scrolls = 50
        last_count = 0
        same_count_times = 0

        for i in range(max_scrolls):

            if not job.running:
                break

            # 🔹 human-like random scroll
            scroll_amount = random.randint(800, 1600)

            page.mouse.wheel(0, scroll_amount)

            # 🔹 random pause (very important)
            time.sleep(random.uniform(2.5, 5.5))

            # 🔹 collect posts
            links = page.evaluate("""
                Array.from(document.querySelectorAll('a'))
                    .map(a => a.href)
                    .filter(h => h.includes('/p/') || h.includes('/reel/'))
            """)

            new_posts = 0

            for link in links:
                link = link.split("?")[0]

                if link not in job.posts:
                    job.posts.append(link)
                    new_posts += 1

            # 🔹 debug only when new posts appear
            if new_posts > 0:
                debug(job.chat_id, f"[{job.username}] posts: {len(job.posts)} (+{new_posts})")

            log(f"posts: {len(job.posts)} (+{new_posts})")

            # 🔴 STOP CONDITION (VERY IMPORTANT)
            if len(job.posts) == last_count:
                same_count_times += 1
            else:
                same_count_times = 0

            last_count = len(job.posts)

            # 🔥 if no new posts for 3 scrolls → STOP
            if same_count_times >= 3:
                log("No new posts loading → stopping scroll")
                break

        page.close()

    except Exception as e:
        log(f"Scraper error: {e}")

    finally:
        try:
            page.close()
        except:
            pass

def playwright_worker():
    global PLAYWRIGHT_CONTEXT
    log("Starting browser in worker thread...")

    with sync_playwright() as play:

        browser = play.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context()
        PLAYWRIGHT_CONTEXT = context
        update_playwright_session(context)

        page = context.new_page()
        page.goto("https://www.instagram.com/")

        log("Instagram session activated")
        while True:

            # 🔴 handle control commands FIRST
            while not control_queue.empty():

                cmd = control_queue.get()

                if cmd == "update_session":
                    log("🔄 Updating session in Playwright thread")
                    update_playwright_session(context)

                control_queue.task_done()

            # 🔴 then handle jobs
            job = job_queue.get()

            if job is None:
                break

            try:
                scrape_background(job, context)
            except Exception as e:
                log(f"Worker error: {e}")

            job_queue.task_done()
def extract_username(text):

    text = text.strip()

    # remove query parameters
    text = text.split("?")[0]

    # if full URL
    match = re.search(r"instagram\.com/([^/]+)/?", text)

    if match:
        return match.group(1).lower()

    # if just username
    if re.match(r"^[a-zA-Z0-9._]+$", text):
        return text.lower()

    return None
# =========================
# START COMMAND
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    bot.send_message(
        message.chat.id,
        "Send Instagram username"
    )
class Job:
    def __init__(self, username, chat_id):
        self.username = username
        self.chat_id = chat_id
        self.posts = []
        self.sent = 0
        self.running = True
        self.status = "created"
user_jobs ={}
job_queue = Queue()
# =========================
# USERNAME HANDLER
# =========================
FAIL_COUNT = 0
@bot.message_handler(func=lambda m: True)
def profile_handler(message):

    global CURRENT_SESSION, LAST_SESSION_CHECK

    # =========================
    # STEP 1: HANDLE SESSION INPUT
    # =========================
    if WAITING_SESSION.get(message.chat.id):

        new_session = message.text.strip()

        if is_session_valid(new_session):

            CURRENT_SESSION = new_session

            # update instaloader
            L.context._session.cookies.set(
                "sessionid",
                CURRENT_SESSION,
                domain=".instagram.com"
            )

            # update playwright
            control_queue.put("update_session")

            WAITING_SESSION[message.chat.id] = False

            bot.send_message(message.chat.id, "✅ Session updated successfully!")

        else:
            bot.send_message(message.chat.id, "❌ Invalid session. Send again.")
            return

        return  # IMPORTANT: stop here

    # =========================
    # STEP 2: CHECK SESSION (with cooldown)
    # =========================
    current_time = time.time()

    if current_time - LAST_SESSION_CHECK > SESSION_CHECK_INTERVAL:

        LAST_SESSION_CHECK = current_time

        if not is_session_valid(CURRENT_SESSION):

            WAITING_SESSION[message.chat.id] = True

            bot.send_message(
                message.chat.id,
                "❌ Session expired.\nSend new sessionid."
            )
            return

    # =========================
    # STEP 3: NORMAL USER INPUT
    # =========================
    username = extract_username(message.text)

    if not username:
        bot.send_message(
            message.chat.id,
            "❌ Invalid input.\n\nSend username or profile link."
        )
        return

    # =========================
    # STEP 4: START JOB
    # =========================
    job = Job(username, message.chat.id)
    user_jobs[message.chat.id] = job

    bot.send_message(
        message.chat.id,
        "Collecting posts...\nPlease wait..."
    )

    job_queue.put(job)

    wait_time = 0
    while len(job.posts) == 0 and wait_time < 20:
        time.sleep(2)
        wait_time += 2

    # =========================
    # STEP 5: FAILURE HANDLING
    # =========================
    
    if len(job.posts) == 0:
        global FAIL_COUNT
        FAIL_COUNT += 1

        if FAIL_COUNT >= 1:
            bot.send_message(
                message.chat.id,
                "⚠️ Critical error. Restarting bot..."
            )

        time.sleep(2)

        restart_bot()
    else:
        # check session FIRST
        if not is_session_valid(CURRENT_SESSION):

            WAITING_SESSION[message.chat.id] = True

            bot.send_message(
                message.chat.id,
                "❌ Session expired.\nSend new sessionid."
            )
            return

        # otherwise restart system
        # bot.send_message(
        #     message.chat.id,
        #     "⚠️ System error. Restarting bot..."
        # )

        # time.sleep(2)
        
        # restart_bot()
        # return

    # =========================
    # STEP 6: SUCCESS
    # =========================
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Download 10 Posts", callback_data="next"),
        InlineKeyboardButton("Cancel", callback_data="cancel")
    )

    bot.send_message(
        message.chat.id,
        f"✅ {len(job.posts)} posts ready.",
        reply_markup=markup
    )
# =========================
# CANCEL
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel(call):

    job = user_jobs.get(call.message.chat.id)

    if job:
        job.running = False

    bot.send_message(call.message.chat.id,"Scraping stopped.")

# =========================
# SEND POSTS
# =========================
@bot.callback_query_handler(func=lambda call: call.data == "next")
def send_next(call):

    job = user_jobs.get(call.message.chat.id)

    if not job:
        bot.send_message(call.message.chat.id, "No active job")
        return

    start = job.sent
    end = start + 10
    posts = job.posts[start:end]
    bot.send_message(call.message.chat.id, "Downloading media...")

    # if not posts:
    #     bot.send_message(call.message.chat.id, "Still collecting posts...")
    #     return

    from io import BytesIO
    from PIL import Image

    for post_url in posts:

        try:

            log(f"Processing: {post_url}")

            post = get_post_from_url(post_url)

            if not post:
                bot.send_message(call.message.chat.id, f"⚠️ Could not load post\n{post_url}")
                continue

            medias = extract_media(post)

            if not medias:
                bot.send_message(call.message.chat.id, f"⚠️ No media found\n{post_url}")
                continue

            for media_type, media_url in medias:

                try:

                    log(f"Checking post: {post}")
                    log(f"Media type: {media_type}")
                    log(f"Media URL: {media_url}")

                    if not media_url:
                        bot.send_message(call.message.chat.id, f"⚠️ Empty media URL\n{post_url}")
                        continue

                    media_url = media_url.replace("&amp;", "&")
                    media_url = media_url.replace(".heic", ".jpg")

                    log(f"Final media URL: {media_url}")

                    response = requests.get(media_url, timeout=30, stream=True)

                    if response.status_code != 200:
                        raise Exception(f"Media download failed (HTTP {response.status_code})")

                    file = BytesIO(response.content)

                    if media_type == "video":

                        file.name = "video.mp4"

                        bot.send_video(
                            call.message.chat.id,
                            file,
                            width=720,
                            height=1280,
                            supports_streaming=True
                        )

                    else:

                        img = Image.open(file).convert("RGB")

                        jpeg = BytesIO()
                        img.save(jpeg, format="JPEG")
                        jpeg.seek(0)

                        bot.send_photo(
                            call.message.chat.id,
                            jpeg,
                        )

                    time.sleep(random.uniform(1.5, 3))

                except Exception as e:

                    error_text = str(e)

                    log(f"Media error: {error_text}")

                    bot.send_message(
                        call.message.chat.id,
                        f"❌ Failed to send media\n\nPost:\n{post_url}\n\nReason:\n{error_text}"
                    )

        except Exception as e:

            error_text = str(e)

            log(f"Post processing error: {error_text}")

            bot.send_message(
                call.message.chat.id,
                f"⚠️ Error processing post\n\nPost:\n{post_url}\n\nReason:\n{error_text}"
            )
            time.sleep(random.uniform(1.5, 3))

           

    job.sent += len(posts)

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Next 10", callback_data="next"),
        InlineKeyboardButton("Cancel", callback_data="cancel")
    )

    bot.send_message(
        call.message.chat.id,
        f"Sent {job.sent} posts",
        reply_markup=markup
    )
# =========================
# RUN BOT
# =========================
print("Bot started")

# start playwright worker
threading.Thread(
    target=playwright_worker,
    daemon=True
).start()

bot.infinity_polling()
