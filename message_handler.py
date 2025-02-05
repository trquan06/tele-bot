# message_handler.py

import os
import asyncio
from pyrogram import Client, filters, errors
from config import BASE_DOWNLOAD_FOLDER, SUPPORTED_MEDIA_TYPES
from download import download_from_url, download_with_progress
from flood_control import handle_flood_wait


# Hàm debug (có thể in ra thông tin để kiểm tra tin nhắn)
def log_message_info(message):
    print("Received message:")
    print(f" - Message ID: {message.message_id}")
    print(f" - Has photo: {bool(message.photo)}")
    print(f" - Has video: {bool(message.video)}")
    print(f" - Has document: {bool(message.document)}")
    if message.text:
        print(f" - Text: {message.text}")

# Xử lý tin nhắn tự động (không cần download mode)
@app.on_message(filters.private | filters.group)
async def handle_message(client, message):
    try:
        # In ra thông tin tin nhắn để debug
        log_message_info(message)

        # Nếu tin nhắn có text bắt đầu bằng http -> xử lý download từ URL
        if message.text and message.text.strip().startswith("http"):
            url = message.text.strip()
            await download_from_url(message, url)
            return

        tasks = []
        # Nếu tin nhắn có ảnh
        if message.photo:
            print("Processing photo...")
            tasks.append(download_with_progress(message, "ảnh"))
        # Nếu tin nhắn có video
        elif message.video:
            print("Processing video...")
            tasks.append(download_with_progress(message, "video"))
        # Nếu tin nhắn có file (document)
        elif message.document:
            # Kiểm tra định dạng file có thuộc SUPPORTED_MEDIA_TYPES không
            file_ext = os.path.splitext(message.document.file_name)[1].lower()
            allowed_exts = sum(SUPPORTED_MEDIA_TYPES.values(), [])
            if file_ext in allowed_exts:
                print("Processing document...")
                tasks.append(download_with_progress(message, "file"))
            else:
                await message.reply(f"Định dạng file {file_ext} không được hỗ trợ.")
        else:
            # Nếu tin nhắn không chứa media hay URL, thông báo
            await message.reply("Tin nhắn này không chứa ảnh, video, document, hoặc URL hợp lệ.")

        if tasks:
            # Chạy song song các tác vụ tải xuống nếu có
            await asyncio.gather(*tasks)

    except errors.FloodWait as e:
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Có lỗi xảy ra khi xử lý tin nhắn: {str(e)}")



