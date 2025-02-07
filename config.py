import os
import logging

# Telegram API credentials
API_ID = "21164074"
API_HASH = "9aebf8ac7742705ce930b06a706754fd"
BOT_TOKEN = "7878223314:AAGdrEWvu86sVWXCHIDFqqZw6m68mK6q5pY"

# Download configuration
BASE_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")
CHUNK_SIZE = 1024 * 1024 * 10  # 10 MB chunks for faster downloads
DOWNLOAD_TIMEOUT = 3600  # 1 hour timeout
CONNECT_TIMEOUT = 30    # 30 seconds for connection timeout
MAX_RETRIES = 5  # Retry attempts for large file downloads
EXTRACT_FOLDER = os.path.join(BASE_DOWNLOAD_FOLDER, "extracted")  # Folder for extracted files
MAX_FILE_SIZE = 1024 * 1024 * 1024 * 10  # 10GB maximum file size for downloads
# Concurrency limits
MAX_CONCURRENT_DOWNLOADS = 10

# Supported media types by extension
SUPPORTED_MEDIA_TYPES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'],
    'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'],
    'compressed': ['.zip', '.rar', '.tar', '.gz', '.7z']
}

# Create download folder if it doesn't exist
if not os.path.exists(BASE_DOWNLOAD_FOLDER):
    os.makedirs(BASE_DOWNLOAD_FOLDER)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
