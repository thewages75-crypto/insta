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
FAIL_COUNT = {}
ADMIN_ID = 123455
TOKEN = "8665521420:AAHi0hfMNn3odVDCd9ajMCW_8FwrSz2OQLQ"
bot = telebot.TeleBot(TOKEN, threaded=True)
from queue import Queue

job_queue = Queue()
# =========================
# INSTAGRAM SESSION
# =========================
LAST_SESSION_CHECK = 0
SESSION_CHECK_INTERVAL = 300
IG_SESSIONID = "4555%3APTeNL8atjbF3Xs%3A9%3AAYgfcs9SbBQqnq2YL5l2j5od0mbvk8b74Q"
CURRENT_SESSION = IG_SESSIONID
WAITING_SESSION = {}   # chat_id → True/False
control_queue = Queue()
# =========================
# JOB SYSTEM
def progress_updater(job, chat_id):

    last_count = -1   # 🔥 put here (outside loop)

    while job.running:

        try:
            current = len(job.posts)

            # 🔴 only update if changed
            if current != last_count:

                last_count = current

                text = f"📊 Collected posts: {current}"

                if job.progress_msg_id:
                    bot.edit_message_text(
                        text,
                        chat_id,
                        job.progress_msg_id
                    )
                else:
                    msg = bot.send_message(chat_id, text)
                    job.progress_msg_id = msg.message_id

        except Exception as e:
            log(f"Progress error: {e}")

        time.sleep(10)
def is_session_valid(sessionid):
    try:
        r = requests.get(
            "https://www.instagram.com/accounts/edit/",
            cookies={"sessionid": sessionid},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
            allow_redirects=False
        )

        # logged-in users can access /accounts/edit/
        if r.status_code == 200:
            return True

        return False

    except Exception as e:
        log(f"Session check error: {e}")
        return False
def update_playwright_session(context):
    try:
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

        log("✅ Playwright session updated")

    except Exception as e:
        log(f"Session update error: {e}")
# =========================
# LOG FUNCTION
# =========================



def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")
    
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

L.context._session.cookies.set(
    "sessionid",
    IG_SESSIONID,
    domain=".instagram.com"
)
print("Instaloader session active")
import os
import sys

def restart_bot(chat_id=None):
    try:
        if chat_id:
            bot.send_message(chat_id, "🔄 Restarting bot...")
    except:
        pass

    log("🔄 Restarting...")
    bot.send_message(chat_id,"🔄 Restarting...")

    # 🔥 STOP polling cleanly
    bot.stop_polling()

    time.sleep(2)

    os.execv(sys.executable, ['python'] + sys.argv)
# =========================
# START PLAYWRIGHT
# =========================

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

    try:

        page = context.new_page()

        url = f"https://www.instagram.com/{username}/"

        delay = random.uniform(4,7)
        time.sleep(delay)

        page.goto(url, wait_until="domcontentloaded")

        time.sleep(5)

        log(f"Current URL: {page.url}")
        if "challenge" in page.url:
            log("Instagram triggered a security challenge. Session is blocked.")
            page.close()
            return

        if "accounts/login" in page.url:

            log("❌ Not logged in → updating session and retrying...")

            # 🔥 update session
            update_playwright_session(context)

            page.close()

            # 🔥 retry immediately
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(5)

            log(f"Retry URL: {page.url}")

            if "login" in page.url:
                log("❌ Session still invalid after retry")
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

        for _ in range(20):

            if not job.running:
                break
            log("Scanning page for posts...")
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

            log(f"Collected posts: {len(job.posts)} (+{new_posts})")

            page.evaluate("""
            window.scrollBy({
                top: 1200,
                left: 0,
                behavior: 'smooth'
            });
            """)

            time.sleep(3)

        page.close()

    except Exception as e:
        log(f"Scraper error: {e}")

    finally:
        try:
            page.close()
        except:
            pass

def playwright_worker():

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

        # 🔴 initial session
        update_playwright_session(context)

        page = context.new_page()
        page.goto("https://www.instagram.com/")

        log("Instagram session activated")

        while True:

            # =========================
            # 🔴 STEP 1: HANDLE CONTROL COMMANDS
            # =========================
            while not control_queue.empty():

                cmd = control_queue.get()

                if cmd == "update_session":
                    log("🔄 Updating Playwright session...")
                    update_playwright_session(context)

                control_queue.task_done()

            # =========================
            # 🔴 STEP 2: HANDLE JOBS
            # =========================
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

    markup = InlineKeyboardMarkup()

    if message.chat.id == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("🔍 Check Session", callback_data="check_session")
        )

    bot.send_message(
        message.chat.id,
        "Send Instagram username",
        reply_markup=markup
    )
class Job:
    def __init__(self, username):
        self.username = username
        self.posts = []
        self.sent = 0
        self.running = True
        self.progress_msg_id = None   
user_jobs ={}
job_queue = Queue()
# =========================
# USERNAME HANDLER
# =========================

@bot.message_handler(func=lambda m: True)
def profile_handler(message):

    chat_id = message.chat.id

    # =========================
    # STEP 1: HANDLE SESSION INPUT
    # =========================
    if WAITING_SESSION.get(chat_id):

        new_session = message.text.strip()

        if is_session_valid(new_session):

            global CURRENT_SESSION
            CURRENT_SESSION = new_session

            L.context._session.cookies.set(
                "sessionid",
                CURRENT_SESSION,
                domain=".instagram.com"
            )
            control_queue.put("update_session")
            WAITING_SESSION[chat_id] = False

            bot.send_message(chat_id, "✅ Session updated successfully!")

        else:
            bot.send_message(chat_id, "❌ Invalid session.\nSend again.")
            return

        return

    # =========================
    # STEP 2: CHECK SESSION FIRST
    # =========================
    global LAST_SESSION_CHECK

    now = time.time()

    if now - LAST_SESSION_CHECK > SESSION_CHECK_INTERVAL:
        LAST_SESSION_CHECK = now

        if not is_session_valid(CURRENT_SESSION):

            WAITING_SESSION[chat_id] = True

            bot.send_message(
                chat_id,
                "❌ Session expired.\n\nSend new sessionid."
            )
            return

    # =========================
    # STEP 3: NORMAL INPUT
    # =========================
    username = extract_username(message.text)

    if not username:
        bot.send_message(chat_id, "❌ Invalid input")
        return

    # =========================
    # STEP 4: FAIL COUNT INIT
    # =========================
    if chat_id not in FAIL_COUNT:
        FAIL_COUNT[chat_id] = 0

    # =========================
    # STEP 5: START JOB
    # =========================
    job = Job(username)
    user_jobs[chat_id] = job
    threading.Thread(
        target=progress_updater,
        args=(job, chat_id),
        daemon=True
    ).start()
    bot.send_message(
        chat_id,
        "Collecting posts...\nPlease wait..."
    )

    job_queue.put(job)

    # wait for posts
    wait_time = 0
    while len(job.posts) == 0 and wait_time < 40:
        time.sleep(2)
        wait_time += 2

    # =========================
    # STEP 6: FAILURE HANDLING
    # =========================
    if len(job.posts) == 0:

        FAIL_COUNT[chat_id] += 1

        if FAIL_COUNT[chat_id] < 2:
            bot.send_message(
                chat_id,
                "⚠️ Failed to collect posts.\nRetrying..."
            )

            job_queue.put(job)
            return

        else:
            bot.send_message(
                chat_id,
                "❌ Failed multiple times.\n🔄 Restarting bot..."
            )

            restart_bot(chat_id)
            return

    # =========================
    # STEP 7: SUCCESS
    # =========================
    job.running = False
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("Download 10 Posts", callback_data="next"),
        InlineKeyboardButton("Cancel", callback_data="cancel")
    )

    # 🔴 ADD HERE
    if chat_id == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("🔍 Check Session", callback_data="check_session")
        )

    bot.send_message(
        chat_id,
        f"✅ {len(job.posts)} posts ready. click download button to download now",
        reply_markup=markup
    )
# =========================
# CANCEL
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel(call):

    job = user_jobs.get(call.message.chat.id)

    if job:
        job.running = False   # 🔥 stops progress thread

    bot.send_message(call.message.chat.id, "Scraping stopped.")
#=======================
#CHECK SESSION
#=======================
@bot.callback_query_handler(func=lambda call: call.data == "check_session")
def check_session(call):

    chat_id = call.message.chat.id

    # 🔴 only admin allowed
    if chat_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Not allowed")
        return

    # 🔴 check session
    valid = is_session_valid(CURRENT_SESSION)

    status = "✅ VALID" if valid else "❌ INVALID"

    # 🔒 mask session
    session = CURRENT_SESSION
    masked = session[:6] + "..." + session[-6:] if len(session) > 12 else session

    bot.send_message(
        chat_id,
        f"🔐 Session Status: {status}\n\nSession:\n{masked}"
    )
    if not valid:
        WAITING_SESSION[chat_id] = True
        bot.send_message(chat_id, "❌ Session expired. Send new sessionid.")
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

bot.remove_webhook()   # 🔥 IMPORTANT

threading.Thread(
    target=playwright_worker,
    daemon=True
).start()

bot.infinity_polling(skip_pending=True)
