import os
import subprocess
from config import BASE_DOWNLOAD_FOLDER
from pyrogram import errors

async def upload_to_google_photos(message):
    """
    Uses rclone to upload files from the download folder to a Google Photos album.
    After a successful upload, cleans up local files.
    """
    try:
        album_name = "ONLYFAN"  # Change as needed
        log_file_path = os.path.join(BASE_DOWNLOAD_FOLDER, "error_log.txt")
        
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            result = subprocess.run(
                [
                    "rclone", "copy", BASE_DOWNLOAD_FOLDER, f"GG PHOTO:album/{album_name}",
                    "--transfers=32", "--drive-chunk-size=128M", "--tpslimit=20", "-P"
                ],
                stdout=log_file, stderr=log_file, text=True, encoding="utf-8"
            )

        if result.returncode == 0:
            await message.reply("✅ Upload to Google Photos completed successfully.")
        else:
            await message.reply(f"Upload failed. Check log: {log_file_path}")

        # Clean up local files (except the log file)
        files_deleted = 0
        for root, dirs, files in os.walk(BASE_DOWNLOAD_FOLDER):
            for file in files:
                if file != "error_log.txt":
                    os.remove(os.path.join(root, file))
                    files_deleted += 1
        await message.reply(f"Cleaned up {files_deleted} files from local storage.")

    except errors.FloodWait as e:
        from flood_control import handle_flood_wait
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"❌ Upload error: {str(e)}")
