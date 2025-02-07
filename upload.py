import os
import subprocess
from config import BASE_DOWNLOAD_FOLDER
from pyrogram import errors

# Đường dẫn đầy đủ đến rclone.exe, cập nhật đường dẫn cho phù hợp với hệ thống của bạn
RCLONE_PATH = "C:\\rclone\\rclone.exe"  # <-- Chỉnh sửa đường dẫn nếu cần

# File to store upload errors (each line is a filepath that failed)
UPLOAD_ERROR_LOG = os.path.join(BASE_DOWNLOAD_FOLDER, "upload_errors.txt")

async def upload_to_google_photos(message):
    """
    Uses rclone to upload files from the download folder to a Google Photos album.
    After a successful upload, cleans up local files.
    On error, logs file paths into UPLOAD_ERROR_LOG.
    """
    try:
        album_name = "ONLYFAN"  # Change as needed
        log_file_path = os.path.join(BASE_DOWNLOAD_FOLDER, "rclone_log.txt")
        
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            result = subprocess.run(
                [
                    RCLONE_PATH, "copy", BASE_DOWNLOAD_FOLDER, f"GG PHOTO:album/{album_name}",
                    "--transfers=32", "--drive-chunk-size=128M", "--tpslimit=20", "-P"
                ],
                stdout=log_file, stderr=log_file, text=True, encoding="utf-8"
            )

        if result.returncode == 0:
            await message.reply("✅ Upload to Google Photos completed successfully.")
        else:
            # Log the error into UPLOAD_ERROR_LOG
            with open(UPLOAD_ERROR_LOG, "a", encoding="utf-8") as error_log:
                error_log.write(f"{BASE_DOWNLOAD_FOLDER}\n")
            await message.reply(f"Upload failed. Check log: {log_file_path}\nFailed uploads recorded.")
        
        # Clean up local files (except error log files)
        files_deleted = 0
        for root, dirs, files in os.walk(BASE_DOWNLOAD_FOLDER):
            for file in files:
                if file not in {"rclone_log.txt", "upload_errors.txt"}:
                    os.remove(os.path.join(root, file))
                    files_deleted += 1
        await message.reply(f"Cleaned up {files_deleted} files from local storage.")

    except errors.FloodWait as e:
        from flood_control import handle_flood_wait
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"❌ Upload error: {str(e)}")
        # In case of exception, log all files for retry:
        with open(UPLOAD_ERROR_LOG, "a", encoding="utf-8") as error_log:
            error_log.write(f"{BASE_DOWNLOAD_FOLDER}\n")


async def retry_upload_command(client, message):
    """
    Reads the upload error log and attempts to re-upload all files listed in it.
    After completion, notifies the user and deletes the error log if successful.
    """
    try:
        if not os.path.exists(UPLOAD_ERROR_LOG):
            await message.reply("No failed uploads recorded.")
            return

        # Read the list of folders (or file paths) to re-upload.
        with open(UPLOAD_ERROR_LOG, "r", encoding="utf-8") as error_log:
            lines = [line.strip() for line in error_log if line.strip()]
        
        if not lines:
            await message.reply("No failed uploads recorded.")
            os.remove(UPLOAD_ERROR_LOG)
            return

        summary_msg = await message.reply(f"Retrying upload for {len(lines)} entries from error log...")
        total = len(lines)
        success_count = 0

        # Loop over each recorded folder or file path
        for idx, path in enumerate(lines, 1):
            try:
                # In this example, we use rclone to upload the same folder
                log_file_path = os.path.join(BASE_DOWNLOAD_FOLDER, "rclone_retry_log.txt")
                with open(log_file_path, "w", encoding="utf-8") as log_file:
                    result = subprocess.run(
                        [
                            RCLONE_PATH, "copy", path, f"GG PHOTO:album/ONLYFAN",
                            "--transfers=32", "--drive-chunk-size=128M", "--tpslimit=20", "-P"
                        ],
                        stdout=log_file, stderr=log_file, text=True, encoding="utf-8"
                    )
                if result.returncode == 0:
                    success_count += 1
                await summary_msg.edit_text(f"Retry upload progress: {idx}/{total} completed.")
            except Exception as e:
                await message.reply(f"Error re-uploading {path}: {str(e)}")
        # If all entries have been processed successfully, delete the error log.
        if success_count == total:
            os.remove(UPLOAD_ERROR_LOG)
            await message.reply("All failed uploads retried and completed successfully. Error log deleted.")
        else:
            await message.reply(f"Retry completed: {success_count} successful out of {total} entries. Please check the error log.")

    except Exception as e:
        await message.reply(f"Error during retry upload: {str(e)}")
