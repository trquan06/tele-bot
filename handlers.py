import os
import asyncio
from pyrogram import Client, filters, errors
from config import API_ID, API_HASH, BOT_TOKEN, BASE_DOWNLOAD_FOLDER, MAX_FILE_SIZE
from system_monitor import get_system_stats
from download import download_from_url, download_with_progress, failed_files
from upload import upload_to_google_photos, retry_upload_command
from flood_control import handle_flood_wait, check_flood_wait_status
import time
from datetime import datetime

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

async def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename.strip()

async def get_media_info(message):
    """Extract media information from the message"""
    try:
        if message.video:
            return {
                'type': 'video',
                'file_id': message.video.file_id,
                'file_name': message.video.file_name if message.video.file_name else f"video_{int(time.time())}.mp4",
                'mime_type': message.video.mime_type,
                'file_size': message.video.file_size,
                'duration': message.video.duration
            }
        elif message.photo:
            return {
                'type': 'photo',
                'file_id': message.photo.file_id,
                'file_name': f"photo_{int(time.time())}.jpg",
                'file_size': message.photo.file_size
            }
        elif message.document:
            return {
                'type': 'document',
                'file_id': message.document.file_id,
                'file_name': message.document.file_name,
                'mime_type': message.document.mime_type,
                'file_size': message.document.file_size
            }
        return None
    except Exception as e:
        print(f"Error getting media info: {e}")
        return None

async def update_progress(status_message, current, total, start_time):
    try:
        if total is None:
            return
        
        now = time.time()
        elapsed_time = now - start_time
        speed = current / elapsed_time if elapsed_time > 0 else 0
        progress = (current / total) * 100 if total > 0 else 0
        
        eta = (total - current) / speed if speed > 0 else 0
        
        await status_message.edit_text(
            f"📥 Downloading...\n"
            f"▪️ Progress: {progress:.1f}%\n"
            f"▪️ Speed: {speed/1024/1024:.1f} MB/s\n"
            f"▪️ Downloaded: {current/1024/1024:.1f}/{total/1024/1024:.1f} MB\n"
            f"▪️ ETA: {eta:.0f}s"
        )
    except Exception as e:
        print(f"Error updating progress: {e}")

# Command handlers
@app.on_message(filters.command("start"))
async def start_command(client, message):
    try:
        await message.reply(
            "Welcome to the Improved Telegram Downloader Bot!\n"
            "Available commands:\n"
            "/download - Start download mode or download from a URL\n"
            "/stop - Stop download mode\n"
            "/upload - Sync files to Google Photos\n"
            "/retry_upload - Retry failed uploads\n"
            "/retry_download - Retry failed downloads\n"
            "/status - Show system status\n"
            "/delete - Delete all files in the download folder\n\n"
            "💡 Features:\n"
            "• Supports forwarded videos, photos, and documents\n"
            "• Real-time progress tracking\n"
            "• Automatic file organization\n"
            "• Error recovery system"
        )
    except errors.FloodWait as e:
        await handle_flood_wait(e, message)

@app.on_message(filters.command("status"))
async def status_command(client, message):
    try:
        stats = await get_system_stats()
        is_waiting, remaining_time = await check_flood_wait_status(message.chat.id)
        flood_status = f"⚠️ FloodWait active: {int(remaining_time)}s" if is_waiting else "✅ Normal"
        
        # Count files in download folder
        total_files = len([f for f in os.listdir(BASE_DOWNLOAD_FOLDER) if os.path.isfile(os.path.join(BASE_DOWNLOAD_FOLDER, f))])
        
        await message.reply(
            f"📊 System Status:\n"
            f"CPU: {stats['cpu_usage']}\n"
            f"RAM: {stats['ram_usage']}\n"
            f"Disk: {stats['disk_space']}\n"
            f"Bot Status: {flood_status}\n"
            f"Downloaded Files: {total_files}\n"
            f"Failed Downloads: {len(failed_files)}\n"
            f"Download Mode: {'✅ Active' if downloading else '❌ Inactive'}\n"
            f"Upload Mode: {'✅ Active' if uploading else '❌ Inactive'}"
        )
    except Exception as e:
        await message.reply(f"Error retrieving system status: {str(e)}")

# The rest of your command handlers remain the same...

# Improved forwarded message handler
@app.on_message(filters.forwarded & (filters.photo | filters.video | filters.document))
async def handle_forwarded_message(client, message):
    global downloading
    try:
        if not downloading:
            await message.reply("❌ Download mode is not activated. Use /download to start.")
            return

        media_info = await get_media_info(message)
        if not media_info:
            await message.reply("❌ Unsupported media type")
            return

        # Check file size
        if media_info['file_size'] and media_info['file_size'] > MAX_FILE_SIZE:
            await message.reply(f"❌ File too large! Maximum size is {MAX_FILE_SIZE/1024/1024:.1f}MB")
            return

        # Create a safe filename
        safe_filename = await sanitize_filename(media_info['file_name'])
        file_path = os.path.join(BASE_DOWNLOAD_FOLDER, safe_filename)

        # Start download with progress tracking
        start_time = time.time()
        status_message = await message.reply("⏳ Starting download...")
        
        try:
            await message.download(
                file_path,
                progress=lambda current, total: asyncio.create_task(
                    update_progress(status_message, current, total, start_time)
                )
            )
            
            # Verify the downloaded file
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                duration_str = f" ({media_info['duration']}s)" if 'duration' in media_info else ""
                await status_message.edit_text(
                    f"✅ Download completed!\n"
                    f"📁 Filename: {safe_filename}\n"
                    f"⏱️ Duration{duration_str}\n"
                    f"💾 Size: {media_info['file_size']/1024/1024:.1f}MB"
                )
            else:
                raise Exception("Downloaded file is empty or missing")
                
        except errors.FloodWait as e:
            await handle_flood_wait(e, message)
            failed_files.append({
                "file_path": file_path,
                "message": message,
                "media_type": media_info['type']
            })
        except Exception as e:
            await status_message.edit_text(f"❌ Download failed: {str(e)}")
            failed_files.append({
                "file_path": file_path,
                "message": message,
                "media_type": media_info['type']
            })
            raise e

    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"❌ Error processing forwarded message: {str(e)}")
