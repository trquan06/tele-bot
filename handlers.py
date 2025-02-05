import os
import asyncio
from pyrogram import Client, filters, errors
from config import API_ID, API_HASH, BOT_TOKEN
from system_monitor import get_system_stats
from download import download_from_url, download_with_progress, failed_files
from upload import upload_to_google_photos, retry_upload_command
from flood_control import handle_flood_wait, check_flood_wait_status

# Global state flags
downloading = False
uploading = False

# Initialize the bot client
app = Client(
    "telegram_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=100,
    max_concurrent_transmissions=10
)

# Add get_active_connections method to Client class
def get_active_connections(self):
    return len(self.sessions)

Client.get_active_connections = get_active_connections

# /start command handler
@app.on_message(filters.command("start"))
async def start_command(client, message):
    try:
        await message.reply(
            "Welcome!\n"
            "Available commands:\n"
            "/download - Start download mode or download from a URL\n"
            "/stop - Stop download mode\n"
            "/upload - Sync files to Google Photos\n"           
            "/retry_upload - Retry uploads to Google Photos\n"
            "/retry_download - Retry failed downloads\n"
            "/status - Show system status"
        )
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)

# /status command handler
@app.on_message(filters.command("status"))
async def status_command(client, message):
    try:
        stats = await get_system_stats()
        is_waiting, remaining_time = await check_flood_wait_status(message.chat.id)
        flood_status = f"⚠️ FloodWait active: {int(remaining_time)}s" if is_waiting else "✅ Normal"
        active_downloads = app.get_active_connections()  # Updated to use get_active_connections
        await message.reply(
            f"📊 System Status:\n"
            f"CPU: {stats['cpu_usage']}\n"
            f"RAM: {stats['ram_usage']}\n"
            f"Disk: {stats['disk_space']}\n"
            f"Bot status: {flood_status}\n"
            f"Active downloads: {active_downloads}\n"
            f"Failed downloads: {len(failed_files)}"
        )
    except Exception as e:
        await message.reply(f"Error retrieving system status: {str(e)}")

# /download command handler
@app.on_message(filters.command("download"))
async def download_command(client, message):
    global downloading
    try:
        args = message.text.split(maxsplit=1)
        # If a URL is provided, download directly from URL
        if len(args) > 1:
            url = args[1].strip()
            if url.startswith("http"):
                await download_from_url(message, url)
            else:
                await message.reply("Invalid URL. Please provide a valid URL.")
            return

        # Otherwise, start download mode
        async with asyncio.Lock():
            if downloading:
                await message.reply("A download task is already running.")
                return
            downloading = True
        await message.reply("Download mode activated. Forward messages with media (photo/video/document) to download.")
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error starting download mode: {str(e)}")

# /stop command handler
@app.on_message(filters.command("stop"))
async def stop_command(client, message):
    global downloading
    try:
        async with asyncio.Lock():
            if not downloading:
                await message.reply("No active download tasks.")
                return
            downloading = False
        await message.reply("Download mode deactivated.")
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error stopping download mode: {str(e)}")

# /upload command handler
@app.on_message(filters.command("upload"))
async def upload_command(client, message):
    global uploading
    try:
        if uploading:
            await message.reply("An upload task is already running.")
            return
        uploading = True
        await upload_to_google_photos(message)
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
        uploading = False
    except Exception as e:
        await message.reply(f"Error during upload: {str(e)}")
        uploading = False

# New /retry_upload command handler
@app.on_message(filters.command("retry_upload"))
async def retry_upload_handler(client, message):
    try:
        await retry_upload_command(client, message)
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error during retry upload: {str(e)}")


# /retry_download command handler
@app.on_message(filters.command("retry_download"))
async def retry_download_command(client, message):
    try:
        if not failed_files:
            await message.reply("No failed downloads to retry.")
            return

        status_message = await message.reply(f"Retrying {len(failed_files)} failed downloads...")
        retry_failed = []
        successful_retries = 0

        for file_info in failed_files[:]:
            file_path = file_info["file_path"]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                # Retry download using the original message and media type
                await download_with_progress(file_info["message"], file_info["media_type"], retry=True)
                failed_files.remove(file_info)
                successful_retries += 1
                if successful_retries % 5 == 0:
                    await status_message.edit_text(
                        f"Retried {successful_retries} downloads..."
                    )
            except errors.FloodWait as e:
                await handle_flood_wait(e, message)
            except Exception as e:
                retry_failed.append({"file": file_path, "error": str(e)})
        summary = (
            f"Retry summary:\n"
            f"✅ Successful: {successful_retries}\n"
            f"❌ Failed: {len(retry_failed)}"
        )
        if retry_failed:
            summary += "\n\nErrors:"
            for fail in retry_failed:
                summary += f"\n- {fail['file']}: {fail['error']}"
        await status_message.edit_text(summary)
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error during retry: {str(e)}")


# New logic to detect and process forwarded messages for downloading media
@app.on_message(filters.forwarded & (filters.photo | filters.video | filters.document))
async def handle_forwarded_message(client, message):
    global downloading
    try:
        if not downloading:
            await message.reply("Download mode is not activated. Use /download to start.")
            return

        tasks = []
        if message.photo:
            tasks.append(download_with_progress(message, "ảnh"))
        elif message.video:
            tasks.append(download_with_progress(message, "video"))
        elif message.document:
            tasks.append(download_with_progress(message, "file"))

        if tasks:
            await asyncio.gather(*tasks)

    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error processing forwarded message: {str(e)}")
