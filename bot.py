import os
import time
import asyncio
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    CallbackQuery
)

# Railway Environment Variables ରୁ ଡାଟା ନେବା
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client(
    "video_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

URL_STORAGE = {}


def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = {0: "B", 1: "KB", 2: "MB", 3: "GB"}
    while size >= power and n < 3:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"


def render_progress_bar(percentage: float) -> str:
    completed = int(percentage // 10)
    remaining = 10 - completed
    return f"[{'█' * completed}{'░' * remaining}] {percentage:.1f}%"


async def safe_edit(msg, text):
    try:
        await msg.edit_text(text)
    except Exception:
        pass


async def upload_progress(current, total, status_msg, start_time, last_update):
    now = time.time()
    if now - last_update[0] < 3.5 and current != total:
        return
    last_update[0] = now

    percentage = (current * 100) / total if total else 0
    elapsed_time = max(now - start_time, 1)
    speed = current / elapsed_time
    eta = int((total - current) / speed) if speed > 0 else 0

    bar = render_progress_bar(percentage)
    text = (
        f"📤 **Telegram କୁ ଅପଲୋଡ୍ ହେଉଛି...**\n\n"
        f"`{bar}`\n"
        f"📦 **Size:** `{humanbytes(current)} / {humanbytes(total)}`\n"
        f"⚡ **Speed:** `{humanbytes(speed)}/s`\n"
        f"⏳ **ETA:** `{eta}s`"
    )
    await safe_edit(status_msg, text)


def download_video_sync(url: str, quality: str, output_path: str, loop, status_msg):
    last_edit = [0]

    def ytdl_hook(d):
        if d["status"] == "downloading":
            now = time.time()
            if now - last_edit[0] < 3.5:
                return
            last_edit[0] = now

            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0

            percentage = (downloaded * 100 / total) if total > 0 else 0
            bar = render_progress_bar(percentage)

            text = (
                f"📥 **ଭିଡିଓ ଡାଉନଲୋଡ୍ ହେଉଛି ({quality}p)...**\n\n"
                f"`{bar}`\n"
                f"📦 **Size:** `{humanbytes(downloaded)} / {humanbytes(total)}`\n"
                f"⚡ **Speed:** `{humanbytes(speed)}/s`\n"
                f"⏳ **ETA:** `{eta}s`"
            )
            asyncio.run_coroutine_threadsafe(
                safe_edit(status_msg, text), loop
            )

    if quality == "best":
        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        fmt = (
            f"bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]/"
            f"best[ext=mp4][height<={quality}]/best[height<={quality}]/best"
        )

    ydl_opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ytdl_hook],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            if os.path.exists(base + ".mp4"):
                filename = base + ".mp4"
        title = info.get("title", "Downloaded Video")
        duration = int(info.get("duration") or 0)
        return filename, title, duration


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="🌐 Open VidQuickly in Telegram",
                web_app=WebAppInfo(url="https://vidquickly.com/xhamster-downloader/")
            )
        ]
    ])
    await message.reply_text(
        "👋 **ନମସ୍କାର! ମୁଁ ଏକ Pro Video Downloader Bot।**\n\n"
        "📥 ଭିଡିଓ ଲିଙ୍କ୍ ପଠାନ୍ତୁ, ତା’ପରେ ମନପସନ୍ଦର **Quality (360p, 720p, 1080p)** ବାଛନ୍ତୁ!",
        reply_markup=keyboard
    )


@app.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def link_handler(client, message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply_text("❌ ଦୟାକରି ଏକ ସଠିକ୍ ଭିଡିଓ ଲିଙ୍କ୍ (`https://...`) ପଠାନ୍ତୁ।")
        return

    msg_id = str(message.id)
    URL_STORAGE[msg_id] = url

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 360p", callback_data=f"dl|360|{msg_id}"),
            InlineKeyboardButton("💻 480p", callback_data=f"dl|480|{msg_id}")
        ],
        [
            InlineKeyboardButton("🎬 720p HD", callback_data=f"dl|720|{msg_id}"),
            InlineKeyboardButton("🔥 1080p FHD", callback_data=f"dl|1080|{msg_id}")
        ],
        [
            InlineKeyboardButton("⚡ Best Available", callback_data=f"dl|best|{msg_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"dl|cancel|{msg_id}")
        ]
    ])

    await message.reply_text(
        "🎞️ **ଭିଡିଓ କ୍ୱାଲିଟି ବାଛନ୍ତୁ:**\n"
        "ତଳେ ଥିବା ବଟନ୍‌ରୁ କେଉଁ କ୍ୱାଲିଟିରେ ଡାଉନଲୋଡ୍ କରିବାକୁ ଚାହୁଁଛନ୍ତି କ୍ଲିକ୍ କରନ୍ତୁ:",
        reply_markup=keyboard,
        quote=True
    )


@app.on_callback_query(filters.regex(r"^dl\|"))
async def quality_callback(client, callback_query: CallbackQuery):
    _, quality, msg_id = callback_query.data.split("|")

    if quality == "cancel":
        URL_STORAGE.pop(msg_id, None)
        await callback_query.message.edit_text("🚫 **ଡାଉନଲୋଡ୍ ବାତିଲ୍ କରାଗଲା।**")
        return

    url = URL_STORAGE.get(msg_id)
    if not url:
        await callback_query.answer("⚠️ ଏହି ଲିଙ୍କ୍‌ର ସମୟ ଶେଷ ହୋଇଯାଇଛି! ପୁଣିଥରେ ଲିଙ୍କ୍ ପଠାନ୍ତୁ।", show_alert=True)
        return

    await callback_query.answer(f"{quality}p ଡାଉନଲୋଡ୍ ଆରମ୍ଭ ହେଉଛି...")
    status_msg = await callback_query.message.edit_text("🔍 **ଭିଡିଓ ଲିଙ୍କ୍ ଯାଞ୍ଚ କରାଯାଉଛି...**")

    output_template = os.path.join(DOWNLOAD_DIR, f"{msg_id}_{quality}_%(id)s.%(ext)s")
    file_path = None
    loop = asyncio.get_running_loop()

    try:
        file_path, title, duration = await asyncio.to_thread(
            download_video_sync, url, quality, output_template, loop, status_msg
        )

        start_time = time.time()
        last_update = [0]

        await callback_query.message.reply_video(
            video=file_path,
            caption=f"🎬 **{title}**\n✨ **Quality:** `{quality}p`",
            duration=duration,
            supports_streaming=True,
            progress=upload_progress,
            progress_args=(status_msg, start_time, last_update)
        )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(
            f"⚠️ **ଡାଉନଲୋଡ୍ ବିଫଳ ହେଲା!**\n"
            f"କାରଣ: `{str(e)[:200]}`"
        )

    finally:
        URL_STORAGE.pop(msg_id, None)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


if __name__ == "__main__":
    print("🤖 Bot is running on Railway...")
    app.run()
