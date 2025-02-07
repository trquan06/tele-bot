from pyrogram import Client, filters, types
import os
import time
import mimetypes
import uuid
from asyncio import Lock, Semaphore
import subprocess
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import json
from typing import Optional, List, Dict, Any
import hashlib
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration from config.json
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    API_ID = config['api_id']
    API_HASH = config['api_hash']
    BOT_TOKEN = config['bot_token']
    ALLOWED_USERS = set(config.get('allowed_users', []))  # List of allowed user IDs
    MAX_CONCURRENT_DOWNLOADS = config.get('max_concurrent_downloads', 5)
    CHUNK_SIZE = config.get('chunk_size', 65536)
    GOOGLE_PHOTOS_ALBUM = config.get('google_photos_album', 'ONLYFAN')
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.error(f"Error loading config: {e}")
    raise SystemExit(1)

# Constants and configurations
BASE_DOWNLOAD_FOLDER = Path.home() / "Downloads" / "telegram_downloads"
TEMP_FOLDER = BASE_DOWNLOAD_FOLDER / "temp"
SUPPORTED_MIME_TYPES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
    'video': ['.mp4', '.mkv', '.avi', '.webm', '.mov']
}

# Create necessary directories
BASE_DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

# State management
class DownloadManager:
    def __init__(self):
        self.download_lock = Lock()
        self.download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self.downloading = False
        self.uploading = False
        self.failed_files: List[Dict[str, Any]] = []
        self.download_stats = {
            'total_downloaded': 0,
            'total_failed': 0,
            'total_size': 0
        }
        self._file_registry: Dict[str, Dict[str, Any]] = {}

    async def register_file(self, file_path: str, message_id: int, file_type: str) -> None:
        file_hash = await self._calculate_file_hash(file_path)
        self._file_registry[file_hash] = {
            'path': file_path,
            'message_id': message_id,
            'type': file_type,
            'timestamp': datetime.now().isoformat()
        }
        await self._save_registry()

    @staticmethod
    async def _calculate_file_hash(file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def _save_registry(self) -> None:
        registry_path = BASE_DOWNLOAD_FOLDER / 'file_registry.json'
        async with aiolock:
            with open(registry_path, 'w') as f:
                json.dump(self._file_registry, f, indent=4)

download_manager = DownloadManager()

# Initialize the Telegram bot client
app = Client(
    "telegram_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Decorator for user authorization
def authorized_users_only(func):
    async def wrapper(client, message):
        if not ALLOWED_USERS or message.from_user.id in ALLOWED_USERS:
            return await func(client, message)
        await message.reply("You are not authorized to use this bot.")
        return None
    return wrapper

# Command handlers
@app.on_message(filters.command("start"))
@authorized_users_only
async def start_command(client, message):
    help_text = """
🤖 **Available Commands:**

/download - Start download mode
/stop - Stop download mode
/upload - Sync files to Google Photos
/retry_download - Retry failed downloads
/retry_upload - Retry failed  uploads
/stats - Show download statistics
/cleanup - Clean up temporary files
/help - Show this help message

**Features:**
• Multi-file download support
• Progress tracking
• Auto-retry for failed downloads
• Google Photos integration
• Duplicate file detection
    """
    await message.reply(help_text, parse_mode="markdown")

@app.on_message(filters.command("stats"))
@authorized_users_only
async def stats_command(client, message):
    stats = download_manager.download_stats
    stats_text = (
        f"📊 **Download Statistics**\n\n"
        f"Total Files Downloaded: {stats['total_downloaded']}\n"
        f"Failed Downloads: {stats['total_failed']}\n"
        f"Total Size: {stats['total_size'] / (1024*1024):.2f} MB"
    )
    await message.reply(stats_text, parse_mode="markdown")

@app.on_message(filters.command("cleanup"))
@authorized_users_only
async def cleanup_command(client, message):
    try:
        # Remove temporary files
        for file in TEMP_FOLDER.iterdir():
            if file.is_file():
                file.unlink()
        
        # Clear failed downloads list
        download_manager.failed_files.clear()
        
        await message.reply("🧹 Cleanup completed successfully!")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        await message.reply(f"❌ Error during cleanup: {str(e)}")

@app.on_message(filters.command("download"))
@authorized_users_only
async def download_command(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        url = args[1].strip()
        if url.startswith(("http://", "https://")):
            await download_from_url(message, url)
        else:
            await message.reply("❌ Invalid URL format.")
        return

    async with download_manager.download_lock:
        if download_manager.downloading:
            await message.reply("⚠️ Download mode is already active.")
            return
        download_manager.downloading = True

    await message.reply("✅ Download mode activated. Forward media messages or send URLs to download.")

@app.on_message(filters.command("stop"))
@authorized_users_only
async def stop_command(client, message):
    async with download_manager.download_lock:
        if not download_manager.downloading:
            await message.reply("ℹ️ No active download mode to stop.")
            return
        download_manager.downloading = False
    await message.reply("🛑 Download mode stopped.")

@app.on_message(filters.command("upload"))
@authorized_users_only
async def upload_command(client, message):
    if download_manager.uploading:
        await message.reply("⚠️ Upload already in progress.")
        return

    download_manager.uploading = True
    status_message = await message.reply("🔄 Starting upload to Google Photos...")

    try:
        result = await upload_to_google_photos(status_message)
        if result['success']:
            await status_message.edit(f"✅ Upload completed!\n\n{result['message']}")
        else:
            await status_message.edit(f"❌ Upload failed:\n\n{result['message']}")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await status_message.edit(f"❌ Upload error: {str(e)}")
    finally:
        download_manager.uploading = False

async def upload_to_google_photos(status_message):
    try:
        album_name = GOOGLE_PHOTOS_ALBUM
        log_file = BASE_DOWNLOAD_FOLDER / "upload_log.txt"

        # Use rclone with improved parameters
        cmd = [
            "rclone", "copy",
            str(BASE_DOWNLOAD_FOLDER),
            f"GG PHOTO:album/{album_name}",
            "--transfers=32",
            "--drive-chunk-size=128M",
            "--tpslimit=20",
            "--progress",
            "--stats=1s",
            "--stats-file-name-length=0"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Monitor upload progress
        while True:
            if process.stdout:
                line = await process.stdout.readline()
                if not line:
                    break
                status = line.decode().strip()
                if status:
                    await status_message.edit(f"🔄 Uploading...\n\n{status}")
            await asyncio.sleep(1)

        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Clean up after successful upload
            for file in BASE_DOWNLOAD_FOLDER.iterdir():
                if file.is_file() and file.suffix in [ext for exts in SUPPORTED_MIME_TYPES.values() for ext in exts]:
                    file.unlink()
            return {'success': True, 'message': "Files uploaded and cleaned up successfully"}
        else:
            error_msg = stderr.decode()
            logger.error(f"Upload error: {error_msg}")
            return {'success': False, 'message': f"Upload failed: {error_msg}"}

    except Exception as e:
        logger.error(f"Upload process error: {e}")
        return {'success': False, 'message': f"Error during upload: {str(e)}"}
@app.on_message(filters.command("retry_upload"))
@authorized_users_only
async def retry_upload_command(client, message):
    """
    Command to retry uploading failed files to Google Photos
    Usage: /retry_upload
    """
    if download_manager.uploading:
        await message.reply("⚠️ Upload already in progress. Please wait for it to complete.")
        return

    # Check for failed uploads registry
    failed_uploads_file = BASE_DOWNLOAD_FOLDER / "failed_uploads.json"
    if not failed_uploads_file.exists():
        await message.reply("ℹ️ No failed uploads found to retry.")
        return

    try:
        with open(failed_uploads_file, 'r') as f:
            failed_uploads = json.load(f)

        if not failed_uploads:
            await message.reply("ℹ️ No failed uploads found to retry.")
            return

        download_manager.uploading = True
        status_message = await message.reply("🔄 Retrying upload for failed files...")

        # Filter out files that no longer exist
        valid_files = [f for f in failed_uploads if Path(f['path']).exists()]
        
        if not valid_files:
            await status_message.edit("❌ No valid files found to retry upload.")
            download_manager.uploading = False
            return

        # Create temporary directory for failed files
        retry_temp_dir = TEMP_FOLDER / "retry_upload"
        retry_temp_dir.mkdir(exist_ok=True)

        # Copy failed files to temporary directory
        for file_info in valid_files:
            src_path = Path(file_info['path'])
            dst_path = retry_temp_dir / src_path.name
            try:
                import shutil
                shutil.copy2(str(src_path), str(dst_path))
            except Exception as e:
                logger.error(f"Error copying file {src_path}: {e}")

        # Attempt to upload files
        result = await upload_to_google_photos_with_retry(
            retry_temp_dir,
            status_message,
            max_retries=3
        )

        if result['success']:
            # Clear failed uploads registry
            with open(failed_uploads_file, 'w') as f:
                json.dump([], f)
            
            # Clean up temporary directory
            shutil.rmtree(retry_temp_dir, ignore_errors=True)
            
            await status_message.edit("✅ Successfully re-uploaded all failed files!")
        else:
            # Update failed uploads registry with remaining failed files
            with open(failed_uploads_file, 'w') as f:
                json.dump(result['remaining_files'], f)
            
            await status_message.edit(
                f"⚠️ Retry upload completed with some failures:\n{result['message']}\n"
                f"Use /retry_upload again to retry remaining files."
            )

    except Exception as e:
        logger.error(f"Retry upload error: {e}")
        await status_message.edit(f"❌ Error during retry upload: {str(e)}")
    finally:
        download_manager.uploading = False
        # Clean up temporary directory if it exists
        if 'retry_temp_dir' in locals():
            shutil.rmtree(retry_temp_dir, ignore_errors=True)

async def upload_to_google_photos_with_retry(source_dir, status_message, max_retries=3):
    """
    Helper function to handle upload retries with detailed status tracking
    """
    remaining_files = []
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            cmd = [
                "rclone", "copy",
                str(source_dir),
                f"GG PHOTO:album/{GOOGLE_PHOTOS_ALBUM}",
                "--transfers=32",
                "--drive-chunk-size=128M",
                "--tpslimit=20",
                "--progress",
                "--stats=1s",
                "--stats-file-name-length=0"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Monitor upload progress
            while True:
                if process.stdout:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    status = line.decode().strip()
                    if status:
                        await status_message.edit(
                            f"🔄 Retry {retry_count + 1}/{max_retries}\n"
                            f"Uploading...\n\n{status}"
                        )
                await asyncio.sleep(1)

            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    'success': True,
                    'message': "All files uploaded successfully",
                    'remaining_files': []
                }
            
            # If upload failed, collect failed files
            error_msg = stderr.decode()
            logger.error(f"Upload retry {retry_count + 1} failed: {error_msg}")
            
            # Parse error output to identify failed files
            failed_files = [
                {'path': str(Path(source_dir) / f.name)}
                for f in Path(source_dir).iterdir()
                if f.is_file()
            ]
            remaining_files = failed_files
            
            retry_count += 1
            if retry_count < max_retries:
                await status_message.edit(
                    f"⚠️ Upload attempt {retry_count} failed. "
                    f"Retrying in 5 seconds..."
                )
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Upload retry error: {e}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(5)
            continue

    return {
        'success': False,
        'message': f"Failed after {max_retries} attempts",
        'remaining_files': remaining_files
    }

@app.on_message(filters.media & ~filters.command)
@authorized_users_only
async def handle_media_message(client, message):
    async with download_manager.download_lock:
        if not download_manager.downloading:
            return

    try:
        if message.photo:
            await process_media(message, "photo")
        elif message.video:
            await process_media(message, "video")
        else:
            await message.reply("❌ Unsupported media type")
    except Exception as e:
        logger.error(f"Media handling error: {e}")
        await message.reply(f"❌ Error processing media: {str(e)}")

async def process_media(message, media_type):
    file_id = message.photo.file_id if media_type == "photo" else message.video.file_id
    file_name = f"{uuid.uuid4().hex}{'.jpg' if media_type == 'photo' else '.mp4'}"
    file_path = BASE_DOWNLOAD_FOLDER / file_name

    try:
        async with download_manager.download_semaphore:
            start_time = time.time()
            status_message = await message.reply("⏳ Download starting...")

            # Progress callback
            async def progress(current, total):
                if not status_message:
                    return
                
                try:
                    elapsed_time = time.time() - start_time
                    speed = current / elapsed_time if elapsed_time > 0 else 0
                    progress_text = (
                        f"📥 Downloading {media_type}...\n"
                        f"Progress: {current * 100 / total:.1f}%\n"
                        f"Speed: {speed / 1024:.1f} KB/s"
                    )
                    await status_message.edit(progress_text)
                except Exception as e:
                    logger.warning(f"Progress update error: {e}")

            # Download the file
            await app.download_media(
                message=message,
                file_name=str(file_path),
                progress=progress
            )

            # Register the downloaded file
            await download_manager.register_file(
                str(file_path),
                message.message_id,
                media_type
            )

            download_manager.download_stats['total_downloaded'] += 1
            download_manager.download_stats['total_size'] += file_path.stat().st_size

            await status_message.edit(f"✅ {media_type.capitalize()} downloaded successfully!")

    except Exception as e:
        logger.error(f"Download error: {e}")
        download_manager.failed_files.append({
            'message': message,
            'media_type': media_type,
            'file_path': str(file_path)
        })
        download_manager.download_stats['total_failed'] += 1
        await status_message.edit(f"❌ Download failed: {str(e)}")

async def download_from_url(message, url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    await message.reply(f"❌ Failed to fetch URL (Status: {response.status})")
                    return

                content_type = response.headers.get('Content-Type', '')
                
                # Handle HTML content (for parsing media links)
                if 'text/html' in content_type:
                    return await handle_html_content(message, url, await response.text())

                # Handle direct media files
                ext = mimetypes.guess_extension(content_type.split(';')[0])
                if not ext or not any(ext in types for types in SUPPORTED_MIME_TYPES.values()):
                    await message.reply("❌ Unsupported file type")
                    return

                file_name = f"{uuid.uuid4().hex}{ext}"
                file_path = BASE_DOWNLOAD_FOLDER / file_name

                status_message = await message.reply("⏳ Downloading from URL...")
                start_time = time.time()
                downloaded = 0

                async with file_path.open('wb') as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        
                        if downloaded % (CHUNK_SIZE * 10) == 0:  # Update progress every 10 chunks
                            await status_message.edit(
                                f"📥 Downloading...\n"
                                f"Size: {downloaded / 1024 / 1024:.1f} MB\n"
                                f"Speed: {speed / 1024 / 1024:.1f} MB/s"
                            )

                await status_message.edit("✅ Download completed!")
                
        except Exception as e:
            logger.error(f"URL download error: {e}")
            await message.reply(f"❌ Error downloading from URL: {str(e)}")

async def handle_html_content(message, url, html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    media_links = []

    try:
        # Handle Telegra.ph
        if 'telegra.ph' in url:
            media_links.extend(
                f"https://telegra.ph{tag['src']}" if tag['src'].startswith('/') else tag['src']
                for tag in soup.find_all(['img', 'video'])
            )
            
            if media_links:
                status_message = await message.reply(f"Found {len(media_links)} media files. Starting download...")
                
                for link in media_links:
                    try:
                        await download_from_url(message, link)
                    except Exception as e:
                        logger.error(f"Error downloading media from {link}: {e}")
                        await message.reply(f"❌ Failed to download: {link}")
                        
                await status_message.edit(f"✅ Downloaded {len(media_links)} files from Telegra.ph")
            else:
                await message.reply("❌ No media files found on the page")
                
        # Add support for other sites here if needed
        else:
            await message.reply("❌ Unsupported website")
            
    except Exception as e:
        logger.error(f"HTML content handling error: {e}")
        await message.reply(f"❌ Error processing webpage: {str(e)}")
        
    return media_links
