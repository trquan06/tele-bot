import subprocess
from handlers import app
import os
from config import BASE_DOWNLOAD_FOLDER
from handlers import delete_command
import logging

if __name__ == "__main__":
    print("Bot is starting...")
    # Ensure download folder exists
    if not os.path.exists(BASE_DOWNLOAD_FOLDER):
        os.makedirs(BASE_DOWNLOAD_FOLDER)

    # Check if rclone is installed
    if not os.path.exists("C:\\rclone\\rclone.exe"):
        logging.error("rclone is not installed. Please install rclone and try again.")
        exit(1)
    
    # Check if Google Photos album is accessible
    try:
        result = subprocess.run(
            ["C:\\rclone\\rclone.exe", "lsf", "GG PHOTO:album/ONLYFAN"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            logging.error("Google Photos album is not accessible. Please check your rclone configuration.")
            exit(1)
    except Exception as e:
        logging.error(f"Error checking Google Photos album: {str(e)}")
        exit(1)
    
    app.run()
