from pyrogram import Client, filters
import os
import time
import mimetypes
import uuid
import asyncio
import aiohttp
import logging
import json
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
import psutil
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, asdict
from asyncio import Lock, Semaphore, Queue
import subprocess

# Enhanced Configuration
class Config:
    API_ID = "21164074"
    API_HASH = "9aebf8ac7742705ce930b06a706754fd"
    BOT_TOKEN = "7878223314:AAGdrEWvu86sVWXCHIDFqqZw6m68mK6q5pY"
    MAX_CONCURRENT_DOWNLOADS = 10
    MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
    ALLOWED_USERS: Set[int] = set()  # Add authorized user IDs here
    SUPPORTED_FORMATS = {
        'images': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'},
        'videos': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'},
        'archives': {'.zip', '.rar', '.tar', '.gz', '.7z'}
    }
    GOOGLE_PHOTOS_ALBUM = "ONLYFAN"

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DownloadTask:
    message_id: int
    file_path: str
    media_type: str
    size: int
    status: str
    start_time: float
    retries: int = 0

class DownloadManager:
    def __init__(self):
        self.download_lock = Lock()
        self.download_semaphore = Semaphore(Config.MAX_CONCURRENT_DOWNLOADS)
        self.downloading = False
        self.uploading = False
        self.failed_downloads: List[DownloadTask] = []
        self.failed_uploads: List[str] = []
        self.download_queue = Queue()
        self.active_downloads: Dict[int, DownloadTask] = {}
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_size': 0
        }
        self.base_path = Path.home() / "Downloads" / "TelegramMedia"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.temp_path = self.base_path / "temp"
        self.temp_path.mkdir(exist_ok=True)

    async def start_download(self, message, media_type: str) -> None:
        if not self._is_user_authorized(message.from_user.id):
            await message.reply("Unauthorized access. Please contact the administrator.")
            return

        file_size = self._get_media_size(message)
        if file_size > Config.MAX_FILE_SIZE:
            await message.reply(f"File too large. Maximum size allowed: {Config.MAX_FILE_SIZE/(1024*1024*1024):.2f}GB")
            return

        task = DownloadTask(
            message_id=message.message_id,
            file_path=self._generate_file_path(media_type),
            media_type=media_type,
            size=file_size,
            status="pending",
            start_time=time.time()
        )
        
        await self.download_queue.put((message, task))
        await self._process_download_queue()

    async def _process_download_queue(self) -> None:
        while not self.download_queue.empty():
            message, task = await self.download_queue.get()
            async with self.download_semaphore:
                try:
                    await self._download_with_progress(message, task)
                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    self.failed_downloads.append(task)
                finally:
                    self.download_queue.task_done()

    async def _download_with_progress(self, message, task: DownloadTask) -> None:
        task.status = "downloading"
        self.active_downloads[task.message_id] = task
        
        try:
            start_time = time.time()
            
            async def progress_callback(current: int, total: int) -> None:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                percentage = (current / total) * 100 if total > 0 else 0
                
                # Update progress every second to avoid flood
                if elapsed_time % 1 < 0.1:
                    await message.edit_text(
                        f"Downloading {task.media_type}...\n"
                        f"Progress: {percentage:.1f}%\n"
                        f"Speed: {speed/1024/1024:.2f} MB/s"
                    )

            await message.download(
                file_name=task.file_path,
                progress=progress_callback
            )
            
            # Verify downloaded file
            if self._verify_file(task.file_path):
                task.status = "completed"
                self.stats['successful_downloads'] += 1
                self.stats['total_size'] += task.size
            else:
                raise Exception("File verification failed")

        except Exception as e:
            task.status = "failed"
            self.stats['failed_downloads'] += 1
            logger.error(f"Download failed for message {task.message_id}: {e}")
            self.failed_downloads.append(task)
        
        finally:
            self.active_downloads.pop(task.message_id, None)
            self.stats['total_downloads'] += 1

    def _verify_file(self, file_path: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                # Read first and last 1024 bytes to verify file integrity
                f.seek(0)
                f.read(1024)
                f.seek(-1024, 2)
                f.read(1024)
            return True
        except Exception:
            return False

    @staticmethod
    def _is_user_authorized(user_id: int) -> bool:
        return len(Config.ALLOWED_USERS) == 0 or user_id in Config.ALLOWED_USERS

    @staticmethod
    def _get_media_size(message) -> int:
        if message.photo:
            return message.photo.file_size
        elif message.video:
            return message.video.file_size
        return 0

    def _generate_file_path(self, media_type: str) -> str:
        ext = '.jpg' if media_type == 'photo' else '.mp4'
        return str(self.base_path / f"{uuid.uuid4().hex}{ext}")

class TelegramBot:
    def __init__(self):
        self.app = Client(
            "telegram_downloader",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN
        )
        self.download_manager = DownloadManager()
        self._setup_handlers()

    def _setup_handlers(self):
        @self.app.on_message(filters.command("start"))
        async def start_command(client, message):
            welcome_text = (
                "Welcome! Available commands:\n"
                "/download - Start download mode or download from URL\n"
                "/stop - Stop download mode\n"
                "/upload - Sync files to Google Photos\n"
                "/retry_upload - Retry failed uploads\n"
                "/retry_download - Retry failed downloads\n"
                "/status - Show system status\n"
                "/delete - Delete all files in download folder\n"
                "/stats - Show download statistics\n"
                "/cleanup - Clean temporary files"
            )
            await message.reply(welcome_text)

        @self.app.on_message(filters.command("status"))
        async def status_command(client, message):
            # Get system statistics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status_text = (
                f"System Status:\n"
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory Usage: {memory.percent}%\n"
                f"Disk Usage: {disk.percent}%\n"
                f"Active Downloads: {len(self.download_manager.active_downloads)}\n"
                f"Failed Downloads: {len(self.download_manager.failed_downloads)}\n"
                f"Failed Uploads: {len(self.download_manager.failed_uploads)}"
            )
            await message.reply(status_text)

        @self.app.on_message(filters.command("stats"))
        async def stats_command(client, message):
            stats = self.download_manager.stats
            stats_text = (
                f"Download Statistics:\n"
                f"Total Downloads: {stats['total_downloads']}\n"
                f"Successful: {stats['successful_downloads']}\n"
                f"Failed: {stats['failed_downloads']}\n"
                f"Total Size: {stats['total_size']/1024/1024/1024:.2f}GB"
            )
            await message.reply(stats_text)

        @self.app.on_message(filters.command("cleanup"))
        async def cleanup_command(client, message):
            try:
                # Remove temporary files
                for file in self.download_manager.temp_path.glob("*"):
                    file.unlink()
                await message.reply("Temporary files cleaned successfully.")
            except Exception as e:
                await message.reply(f"Error during cleanup: {e}")
@app.on_message(filters.command("download"))
async def download_command(client, message):
    # Check if the command includes a URL
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        url = args[1].strip()
        if url.startswith("http"):
            await download_from_url(message, url)
        else:
            await message.reply("URL không hợp lệ. Hãy đảm bảo bạn nhập đúng định dạng URL.")
        return

    # Enter download mode
    global downloading
    async with download_lock:
        if downloading:
            await message.reply("Đã có tác vụ tải về đang chạy.")
            return
        downloading = True

    await message.reply("Bắt đầu chế độ tải về. Forward tin nhắn chứa ảnh/video để tải về.")

@app.on_message(filters.command("stop"))
async def stop_command(client, message):
    # Exit download mode
    global downloading
    async with download_lock:
        if not downloading:
            await message.reply("Không có tác vụ tải về nào đang chạy.")
            return
        downloading = False
    await message.reply("Đã ngừng chế độ tải về.")

        @self.app.on_message(filters.command("upload"))
        async def upload_command(client, message):
            """
            Handler for the upload command that synchronizes files to Google Photos.
            Includes proper authorization checks and status updates.
            """
            # Authorization check
            if not self.download_manager._is_user_authorized(message.from_user.id):
                await message.reply("Unauthorized access. Please contact the administrator.")
                return

            # Check if upload is already in progress
            if self.download_manager.uploading:
                await message.reply("An upload task is already in progress.")
                return

            # Set upload flag and begin process
            self.download_manager.uploading = True
            try:
                await message.reply("Starting file synchronization to Google Photos...")
                await self._upload_files_to_google_photos(message)
            except Exception as e:
                logger.error(f"Upload process failed: {e}")
                await message.reply(f"Upload process encountered an error: {str(e)}")
            finally:
                self.download_manager.uploading = False

    async def _upload_files_to_google_photos(self, message):
        """
        Helper method to handle the file upload process to Google Photos.
        Includes progress tracking and error handling.
        """
        # Scan for files to upload
        files_to_upload = list(self.download_manager.base_path.glob("*.*"))
        if not files_to_upload:
            await message.reply("No files found to upload.")
            return

        total_files = len(files_to_upload)
        uploaded_files = 0
        
        # Process each file
        for file_path in files_to_upload:
            if file_path.suffix.lower() in {ext for formats in Config.SUPPORTED_FORMATS.values() 
                                          for ext in formats}:
                try:
                    # Create upload task
                    task = UploadTask(
                        file_path=str(file_path),
                        status="pending",
                        start_time=time.time()
                    )
                    
                    # Execute upload using rclone
                    process = await asyncio.create_subprocess_exec(
                        "rclone", "copy",
                        str(file_path),
                        f"GG PHOTO:album/{Config.GOOGLE_PHOTOS_ALBUM}",
                        "--transfers=32",
                        "--drive-chunk-size=128M",
                        "--tpslimit=20",
                        "-P",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        uploaded_files += 1
                        task.status = "completed"
                        # Log successful upload
                        logger.info(f"Successfully uploaded: {file_path}")
                    else:
                        task.status = "failed"
                        task.error_message = stderr.decode()
                        self.download_manager.failed_uploads.append(task)
                        logger.error(f"Failed to upload {file_path}: {task.error_message}")
                
                except Exception as e:
                    logger.error(f"Error uploading {file_path}: {e}")
                    task.status = "failed"
                    task.error_message = str(e)
                    self.download_manager.failed_uploads.append(task)
                
                # Update progress for user
                progress = (uploaded_files / total_files) * 100
                await message.reply(
                    f"Upload progress: {progress:.1f}% ({uploaded_files}/{total_files} files)"
                )

        # Provide final status report
        if self.download_manager.failed_uploads:
            failed_count = len(self.download_manager.failed_uploads)
            await message.reply(
                f"Upload completed with {failed_count} failures.\n"
                f"Successfully uploaded: {uploaded_files} files\n"
                f"Failed uploads: {failed_count} files\n"
                "Use /retry_upload to retry failed uploads."
            )
        else:
            await message.reply(
                f"Successfully uploaded all {uploaded_files} files to Google Photos!"
            )
@app.on_message(filters.command("retry_download"))
async def retry_download_command(client, message):
    # Retry downloading failed files
    global failed_files

    if not failed_files:
        await message.reply("Không có file bị lỗi nào để tải lại.")
        return

    await message.reply("Bắt đầu tải lại các file bị lỗi...")

    for file_info in failed_files:
        file_path = file_info["file_path"]
        try:
            if os.path.exists(file_path):
                os.remove(file_path)

            await download_with_progress(file_info["message"], file_info["media_type"], retry=True)
        except Exception as e:
            await message.reply(f"Có lỗi khi tải lại file: {file_path}\nChi tiết: {e}")

    failed_files.clear()
    await message.reply("Hoàn thành tải lại các file bị lỗi.")

@app.on_message()
async def handle_message(client, message):
    # Handle forwarded messages for download mode
    global downloading
    async with download_lock:
        if not downloading:
            return

    if message.text and message.text.startswith("http"):
        url = message.text.strip()
        await download_from_url(message, url)
        return

    if message.photo or message.video:
        try:
            tasks = []
            if message.photo:
                tasks.append(download_with_progress(message, "ảnh"))
            elif message.video:
                tasks.append(download_with_progress(message, "video"))
            await asyncio.gather(*tasks)
        except Exception as e:
            await message.reply(f"Có lỗi xảy ra khi xử lý tin nhắn: {e}")
    else:
        await message.reply("Tin nhắn này không chứa ảnh, video, hoặc URL hợp lệ.")

async def download_with_progress(message, media_type, retry=False):
    # Download media with a progress bar
    global failed_files

    file_name = f"{uuid.uuid4().hex}.{ 'jpg' if media_type == 'ảnh' else 'mp4' }"
    file_path = os.path.join(BASE_DOWNLOAD_FOLDER, file_name)

    start_time = time.time()

    async def progress_callback(current, total):
        # Show download progress
        elapsed_time = time.time() - start_time
        speed = current / elapsed_time if elapsed_time > 0 else 0
        if current == total:
            await message.reply(
                f"Tải xong {media_type}: 100% ({total / (1024 * 1024):.2f} MB)\n"
                f"Tốc độ: {speed / 1024:.2f} KB/s",
                quote=True
            )

    try:
        async with download_semaphore:
            await app.download_media(
                message.photo or message.video,
                file_name=file_path,
                progress=progress_callback
            )
    except Exception as e:
        failed_files.append({"message": message, "media_type": media_type, "file_path": file_path})
        await message.reply(f"Tải file bị lỗi: {e}\nFile đã được thêm vào danh sách retry.", quote=True)

async def download_from_url(message, url):
    # Download content from a URL
    failed_downloads = []
    connector = aiohttp.TCPConnector(limit=50)  # Increase connection limit
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url) as response:
                if response.status == 200 and "html" in response.headers.get("Content-Type", ""):
                    # Parse HTML for images/videos
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")

                    if "telegra.ph" in url:
                        media_links = [
                            tag["src"] for tag in soup.find_all("img", src=True)
                        ]
                        if not media_links:
                            await message.reply("Không tìm thấy ảnh trong URL Telegra.ph.")
                            return

                        for media_url in media_links:
                            if media_url.startswith("/"):
                                media_url = f"https://telegra.ph{media_url}"
                            await download_from_url(message, media_url)
                        return

                    media_links = [
                        tag["src"] for tag in soup.find_all(["img", "video"], src=True)
                    ]

                    if media_links:
                        for media_url in media_links:
                            if not media_url.startswith("http"):
                                media_url = os.path.join(os.path.dirname(url), media_url)
                            await download_from_url(message, media_url)
                        return
                    else:
                        await message.reply("Không tìm thấy ảnh hoặc video trong URL được cung cấp.")
                        return

                # Handle server errors
                if response.status == 500:
                    await message.reply(f"Lỗi server (500) từ URL: {url}. Vui lòng thử lại sau.")
                    return

                if response.status != 200:
                    await message.reply(f"Không thể tải file từ URL: {url}\nMã lỗi: {response.status}")
                    return

                content_type = response.headers.get("Content-Type", "")
                ext = mimetypes.guess_extension(content_type.split(";")[0]) or ""
                file_name = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join(BASE_DOWNLOAD_FOLDER, file_name)

                with open(file_path, "wb") as f:
                    while chunk := await response.content.read(65536):  # Increased chunk size
                        f.write(chunk)

                await message.reply(f"Tải thành công file từ URL: {url}\nĐã lưu tại: {file_path}")
        except Exception as e:
            failed_downloads.append(url)
            await message.reply(f"Có lỗi xảy ra khi tải file từ URL: {e}")

  def run(self):
        logger.info("Bot is starting...")
        self.app.run()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()



