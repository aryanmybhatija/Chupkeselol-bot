import os
import time
import shutil
import traceback
import logging
import json
import re
import requests
import asyncio
from threading import Thread
from urllib.parse import quote
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from dotenv import load_dotenv
from flask import Flask, render_template
from auth import add_authorized_user, remove_authorized_user, is_authorized, AUTHORIZED_USERS, AUTHORIZED_USERS_FILE
from auth import BOT_OWNER_ID, get_authorized_users
from utils.duration import get_video_duration, sanitize_filename

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID", ""))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", ""))
# 🖇️ Terabox api
TERABOX_API = os.getenv("TERABOX_API", "https://angel-noor-terabox-api.woodmirror.workers.dev/api?url=")
# 🔗 Channel button photo links
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "⚡Team Sonu ™")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/Team_Sonu2")
WELCOME_URL = os.getenv("WELCOME_URL", "https://ar-hosting.pages.dev/1751519807441.jpg")
USER_URL = os.getenv("PHOTO_URL", "https://ar-hosting.pages.dev/1751519808272.jpg")
# ⭐ Read max size in MB default = 1900 MB
MAX_SIZE_MB = int(os.getenv("MAX_SIZE", 1900))
# 💥 Convert MB to bytes
MAX_SIZE = MAX_SIZE_MB * 1024 * 1024
# ▶️ Video Streaming Support
SUPPORTS_STREAMING = os.getenv("SUPPORTS_STREAMING", "True").lower() == "true"
HAS_SPOILER = os.getenv("HAS_SPOILER", "False").lower() == "true"

# Initialize Pyrogram client
bot = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Constants
DOWNLOAD_DIR = "downloads"
PROGRESS_UPDATE_INTERVAL = 1  # 1 second interval for smoother progress

# Regex pattern for Terabox links
TERABOX_REGEX = r"https?://(?:www\.)?(teraboxlink\.com|terasharelink\.com|teraboxapp\.com|1024terabox\.com|terabox\.com|terasharelink\.com|terafileshare\.com|4funbox\.co|teraboxapp\.to|terabox\.app)/s/([a-zA-Z0-9_-]+)"

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("terabox_bot")

# Add file logging handler
file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# Initialize Flask app
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return render_template("index.html")
    
Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080), daemon=True).start()

# Utility functions
def human_readable_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

def progress_bar(percentage, bar_length=20):
    """Fixed progress bar function"""
    filled = int(bar_length * percentage / 100)
    empty = bar_length - filled
    return "█" * filled + "░" * empty

async def edit_message(message, text):
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await edit_message(message, text)
    except Exception as e:
        logger.error(f"Error editing message: {str(e)}")

async def delete_message(message):
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {str(e)}")

def clean_directory(directory):
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            logger.info(f"🪥 Successfully cleaned your file: {directory}")
            return True
        else:
            logger.warning(f"⚠️ Directory does not exist: {directory}")
            return False
    except Exception as e:
        logger.error(f"❌ Error cleaning directory {directory}: {repr(e)}")
        logger.debug(traceback.format_exc())
        return False

def parse_aria2c_output(line):
    """Parse aria2c output to get download progress"""
    try:
        # Example: [#1c9b1b 20MiB/100MiB(20%) CN:1 DL:3.0MiB]
        match = re.search(r'\((\d+)%\)', line)
        if match:
            return int(match.group(1))
        return None
    except Exception:
        return None
        
# Terabox processing
async def process_terabox(user_id, terabox_url, msg):
    USER_DIR = os.path.join(DOWNLOAD_DIR, f"user_{user_id}_{int(time.time())}")
    os.makedirs(USER_DIR, exist_ok=True)

    try:
        # Show processing message
        await edit_message(
            msg,
            f"╭━◝━━━━━━━━━━━━◜━╮\n"
            f"⚡❍⊱❁ Team Sonu™\n"
            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
            f"🔍 <b>Processing your link...</b>\n"
            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
        )
        
        # Fetch API data
        api_url = TERABOX_API + quote(terabox_url)
        response = requests.get(api_url)
        
        if response.status_code != 200:
            await edit_message(
                msg,
                f"❌ <b>API Error:</b> Failed to fetch link information\n"
                f"Status Code: {response.status_code}"
            )
            await asyncio.sleep(5)
            await delete_message(msg)
            return False
            
        data = response.json()
        file_name = data["file_name"]
        download_url = data["proxy_url"]
        file_size = data["size_bytes"]
        readable_size = human_readable_size(file_size)
        
        # Check file size
        if file_size > MAX_SIZE:
            await edit_message(
                msg,
                f"❌ <b>File Too Large:</b> {readable_size}\n"
                f"Max allowed: {human_readable_size(MAX_SIZE)}"
            )
            await asyncio.sleep(5)
            await delete_message(msg)
            return False
        
        file_path = os.path.join(USER_DIR, file_name)
        
        # Start download
        await edit_message(
            msg,
            f"╭━◝━━━━━━━━━━━━◜━╮\n"
            f"⚡❍⊱❁ Team Sonu™\n"
            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
            f"📥 <b>Downloading:</b> <code>{file_name}</code>\n"
            f"📦 <b>Size:</b> {readable_size}\n"
            f"🔸 {progress_bar(0)} 🔸\n"
            f"🚀 <b>Progress:</b> 0%\n"
            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
        )
        
        # Download file with improved progress tracking
        command = [
            "aria2c", 
            "-x16", 
            "--summary-interval=1",
            "--auto-file-renaming=false", 
            "--allow-overwrite=true",
            "--dir=" + USER_DIR, 
            "--out=" + file_name, 
            download_url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # Track download progress with aria2c output
        last_reported_percent = 0
        start_time = time.time()
        timeout = 7200  # 2 hours timeout for large files
        
        # Pattern to match aria2c progress output
        progress_pattern = re.compile(r'\((\d+)%\)')
        
        while True:
            # Check if process is still running
            if process.returncode is not None:
                break
                
            # Check timeout
            if time.time() - start_time > timeout:
                process.kill()
                await edit_message(msg, "❌ Download timed out (2 hours)")
                await asyncio.sleep(5)
                await delete_message(msg)
                return False
                
            # Read stdout line by line
            line = await process.stdout.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue
                
            line = line.decode().strip()
            percent_match = progress_pattern.search(line)
            
            if percent_match:
                percent = int(percent_match.group(1))
                # Update progress only when it changes
                if percent > last_reported_percent:
                    bar = progress_bar(percent)
                    
                    try:
                        await edit_message(
                            msg,
                            f"╭━◝━━━━━━━━━━━━◜━╮\n"
                            f"⚡❍⊱❁ Team Sonu ™\n"
                            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
                            f"📥 <b>Downloading:</b> <code>{file_name}</code>\n"
                            f"📦 <b>Size:</b> {readable_size}\n"
                            f"🔸 {bar} 🔸\n"
                            f"🚀 <b>Progress:</b> {percent}%\n"
                            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
                        )
                        last_reported_percent = percent
                    except Exception as e:
                        logger.error(f"Error updating progress: {str(e)}")
            
            await asyncio.sleep(0.1)
        
        # Wait for process to finish
        await process.wait()
        
        # Verify download
        if not os.path.exists(file_path) or os.path.getsize(file_path) < file_size * 0.95:  # 95% tolerance
            await edit_message(
                msg,
                f"❌ <b>Download Failed:</b>\n"
                f"File incomplete or corrupted\n"
                f"Expected: {readable_size}\n"
                f"Actual: {human_readable_size(os.path.getsize(file_path)) if os.path.exists(file_path) else '0 B'}"
            )
            await asyncio.sleep(5)
            await delete_message(msg)
            return False
        
        # Prepare for upload
        await edit_message(
            msg,
            f"╭━◝━━━━━━━━━━━━◜━╮\n"
            f"⚡❍⊱❁ Team Sonu ™\n"
            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
            f"📤 <b>Uploading:</b> <code>{file_name}</code>\n"
            f"📦 <b>Size:</b> {readable_size}\n"
            f"🔸 {progress_bar(0)} 🔸\n"
            f"🚀 <b>Progress:</b> 0%\n"
            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
        )
        
        # Create caption and download button
        caption = (
            f"╭━◝━━━━━━━━━━━━◜━╮\n"
            f"⚡❍⊱❁ Team Sonu ™\n"
            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
            f"<pre>✅ Your File is Ready!</pre>\n\n"
            f"📂 <b>File:</b> <code>{file_name}</code>\n"
            f"📦 <b>Size:</b> {readable_size}\n"
            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
        )
        
        # Create inline keyboard with direct download button
        keyboard = InlineKeyboardMarkup([[  
            InlineKeyboardButton(f"🔗 Direct Download {readable_size}", url=download_url)  
        ]])
        
        # Send file with upload progress
        is_video = file_name.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm'))
        thumb_path = os.path.join(USER_DIR, "thumb.jpg")
        
        if "thumbnail" in data:
            try:
                thumb_data = requests.get(data["thumbnail"]).content
                with open(thumb_path, "wb") as f:
                    f.write(thumb_data)
            except Exception as e:
                logger.warning(f"Thumbnail download failed: {str(e)}")
                thumb_path = None
        
        # Upload progress callback
        last_upload_percent = 0
        
        async def progress_callback(current, total):
            nonlocal last_upload_percent
            percent = int(current * 100 / total)
            
            # Update every 5% or when it changes significantly
            if percent > last_upload_percent + 5 or percent == 100:
                bar = progress_bar(percent)
                try:
                    await edit_message(
                        msg,
                        f"╭━◝━━━━━━━━━━━━◜━╮\n"
                        f"⚡❍⊱❁ Team Sonu ™\n"
                        f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
                        f"📤 <b>Uploading:</b> <code>{file_name}</code>\n"
                        f"📦 <b>Size:</b> {readable_size}\n"
                        f"🔸 {bar} 🔸\n"
                        f"🚀 <b>Progress:</b> {percent}%\n"
                        f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨"
                    )
                    last_upload_percent = percent
                except Exception as e:
                    logger.error(f"Error updating upload progress: {str(e)}")
        
        try:
            # Calculate upload timeout based on file size
            upload_timeout = max(600, int(file_size / (50 * 1024 * 1024)) * 60 + 600)  # More generous timeout
            
            if is_video:
                duration = get_video_duration(file_path)
                if duration == 0:
                    logger.warning("⚠️ ffprobe failed to detect duration, setting to None")
                    duration = None
                
                # Use asyncio.wait_for for timeout handling
                await asyncio.wait_for(
                    msg.reply_video(
                        video=file_path,
                        caption=caption,
                        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                        progress=progress_callback,
                        duration=duration,
                        supports_streaming=SUPPORTS_STREAMING,
                        has_spoiler=HAS_SPOILER
                    ),
                    timeout=upload_timeout
                )
            else:
                # Use asyncio.wait_for for timeout handling
                await asyncio.wait_for(
                    msg.reply_document(
                        document=file_path,
                        caption=caption,
                        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                        progress=progress_callback
                    ),
                    timeout=upload_timeout
                )
        except asyncio.TimeoutError:
            logger.error(f"Upload timed out after {upload_timeout} seconds")
            await edit_message(
                msg,
                f"❌ <b>Upload Timeout:</b>\n"
                f"Upload took too long ({upload_timeout}s limit)\n"
                f"Please try again with a smaller file."
            )
            await asyncio.sleep(5)
            await delete_message(msg)
            return False
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            await edit_message(
                msg,
                f"❌ <b>Upload Failed:</b>\n"
                f"{str(e)}"
            )
            await asyncio.sleep(5)
            await delete_message(msg)
            return False
        
        # Delete progress message after successful upload
        await delete_message(msg)
        return True
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        await edit_message(
            msg,
            f"❌ <b>Critical Error:</b>\n"
            f"{str(e)}"
        )
        await asyncio.sleep(5)
        await delete_message(msg)
        return False
    finally:
        if clean_directory(USER_DIR):
            logger.info(f"🧹 Cleaned: {USER_DIR}")
        else:
            logger.warning(f"⚠️ Cleanup failed: {USER_DIR}")

# Start command handler
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    caption = (
        "<pre>🔷🔹🔸♦️◈ 𝗧𝗘𝗥𝗔𝗕𝗢𝗫 𝗕𝗢𝗧 ◈♦️🔸🔹🔷</pre>\n\n"
        "📘 <b>How It Works:</b>\n"
        "➤ Paste your Terabox URL below 👇\n"
        "➤ The bot will fetch & send the file ⚡\n\n"
        "🌐 <b>Supported:</b> <i>(Tap the button below)</i>\n\n"
        "📦 <b>Limit:</b> <code>1.9GB</code>\n"
        "<pre>👨‍💻 Created by Team_Sonu</pre>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Supported Domains", callback_data="show_supported_domains")],
        [InlineKeyboardButton(CHANNEL_NAME, url=CHANNEL_URL)]
    ])

    try:
        await message.reply_photo(
            photo=WELCOME_URL,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await start_handler(client, message)

@bot.on_callback_query()
async def callback_query_handler(client, callback_query):
    try:
        if callback_query.data == "show_supported_domains":
            await callback_query.answer(
                "🌍 Supported Domains:\n"
                "💧 terabox.com\n"
                "💧 4funbox.co\n"
                "💧 terabox.app\n"
                "💧 teraboxapp.com\n"
                "💧 teraboxlink.com\n"
                "💧 terafileshare.com\n"
                "💧 terasharelink.com\n"
                "💧 1024terabox.com\n"
                "✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨\n\n"
                "⚡❍⊱❁ Team_Sonu  ™",
                show_alert=True
            )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await callback_query_handler(client, callback_query)

# ✅ Add user command
@bot.on_message(filters.command("adduser"))
async def add_user_cmd(client, message):
    if message.from_user.id != BOT_OWNER_ID:
        return await message.reply("🚫 You cannot run this command.")

    try:
        logger.info("Adduser command triggered")
        args = message.text.split()

        if len(args) < 2:
            return await message.reply("❌ Use: /adduser <user_id>")

        try:
            new_id = int(args[1])
        except ValueError:
            return await message.reply("❌ Invalid user ID! Enter a number.")

        result = add_authorized_user(new_id)

        if result:
            await message.reply(f"✅ User `{new_id}` Added!")

            # ✅ Notify user
            try:
                await client.send_message(new_id, "✅ You've been added to the authorized user list.")
                logger.info(f"Notified user {new_id}")
            except Exception as e:
                logger.warning(f"Couldn't message user {new_id}: {e}")

        else:
            await message.reply(f"ℹ️ User `{new_id}` was already added.")
    except Exception as e:
        logger.exception("Error in adduser")
        await message.reply(f"❌ Error: {str(e)}")

# ✅ Remove user command
@bot.on_message(filters.command("removeuser"))
async def remove_user_cmd(client, message):
    if message.from_user.id != BOT_OWNER_ID:
        return await message.reply("🚫 You cannot run this command.")

    try:
        logger.info("Removeuser command triggered")
        args = message.text.split()

        if len(args) < 2:
            return await message.reply("❌ Use: /removeuser <user_id>")

        try:
            uid = int(args[1])
        except ValueError:
            return await message.reply("❌ Invalid user ID! Enter a number.")

        result = remove_authorized_user(uid)

        if result:
            await message.reply(f"❎ User `{uid}` removed!")
        else:
            await message.reply(f"⚠️ User `{uid}` was not authorized.")
    except Exception as e:
        logger.exception("Error in removeuser")
        await message.reply(f"❌ Error: {str(e)}")

# ✅ Userlist command
@bot.on_message(filters.command("userlist"))
async def list_users(client, message):
    if message.from_user.id != BOT_OWNER_ID:
        logger.warning(f"Unauthorized /userlist access attempt by: {message.from_user.id}")
        return await message.reply("🚫 You cannot run this command.")

    logger.info(f"/userlist command triggered by: {message.from_user.id}")

    try:
        users = get_authorized_users()
        logger.info(f"AUTHORIZED_USERS inside /userlist: {users}")

        if not users:
            logger.warning("User list is empty!")
            return await message.reply("⚠️ There are no authorized users.")

        # ✅ Plain text formatting
        text = "👤 **Authorized User List:**\n"
        text += "═══════════════════════\n"

        for i, uid in enumerate(users, start=1):
            try:
                user = await client.get_users(uid)
                name = user.first_name or "No name"
                logger.info(f"User #{i}: {name} ({uid})")
                text += f"🔹 {i}. {name}\n🆔 {uid}\n\n"
            except Exception as e:
                name = "Name not found (❗Hasn't started the bot)"
                logger.warning(f"User ID {uid} fetch failed: {str(e)}")
                text += f"🔹 {i}. {name}\n🆔 {uid}\n\n"

        text += "═══════════════════════"

        # ✅ Inline button
        developer = InlineKeyboardMarkup([
            [InlineKeyboardButton("💧 Contact 💦", url="https://t.me/Contact_AdminSbot")]
        ])

        # ✅ Try sending with image
        try:
            await message.reply_photo(
                photo=USER_URL,
                caption=text,
                reply_markup=developer
            )
        except Exception as e:
            logger.warning(f"Couldn't send photo: {e}")
            await message.reply(
                text=text,
                reply_markup=developer,
                disable_web_page_preview=True
            )

        logger.info("/userlist executed successfully.")

    except Exception as e:
        logger.exception(f"❌ Error in /userlist command: {str(e)}")
        await message.reply(f"❌ Error: {str(e)}")

# Message handler
@bot.on_message(filters.private & filters.text)
async def message_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if not is_authorized(user_id):
        await message.reply("🚫 You are not authorized to use this bot.")
        return

    if not re.match(TERABOX_REGEX, text):
        try:
            error_msg = await message.reply("❌ Please send a valid Terabox link")
            await asyncio.sleep(10)
            await error_msg.delete()
        except Exception:
            pass
        return

    try:
        msg = await message.reply(
            f"╭━◝━━━━━━━━━━━━◜━╮\n"
            f"⚡❍⊱❁ Team Sonu ™\n"
            f"╰━◞━━━━━━━━━━━━◟━╯\n\n"
            f"🔍 <b>Processing your link...</b>\n"
            f"✨❍⭕️━━━━━━━━━━━━━━━⭕️❍✨",
            parse_mode=ParseMode.HTML
        )
    except FloodWait as e:
        logger.warning(f"FloodWait: Sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)

        if e.value > 600:
            await message.reply("🚫 FloodWait too long. Please try again later.")
            return
        
        # Retry after waiting
        await message_handler(client, message)
        return

    # Proceed only if no FloodWait
    await process_terabox(user_id, text, msg)

# Run the bot
if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    logger.info("🚀 Starting Terabox Downloader Bot...")
    # Log the authorized users file path
    logger.info(f"Authorized users file: {AUTHORIZED_USERS_FILE}")
    logger.info(f"Initial authorized users: {AUTHORIZED_USERS}")

    # Start the bot 💥
    bot.run()
