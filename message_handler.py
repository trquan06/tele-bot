import os
import asyncio
from pyrogram import filters, errors
from config import SUPPORTED_MEDIA_TYPES
from handlers import app, downloading
from download import download_with_progress, download_from_url

@app.on_message()
async def handle_message(client, message):
    """
    Routes incoming messages.
    - If the message text starts with a URL, it calls download_from_url.
    - If the message contains media and download mode is active, it calls download_with_progress.
    """
    try:
        # Only process if download mode is active
        if not downloading:
            return

        # If message contains a URL text
        if message.text and message.text.startswith("http"):
            url = message.text.strip()
            await download_from_url(message, url)
            return

        tasks = []
        if message.photo:
            tasks.append(download_with_progress(message, "ảnh"))
        elif message.video:
            tasks.append(download_with_progress(message, "video"))
        elif message.document:
            # Check if the file extension is supported
            file_ext = os.path.splitext(message.document.file_name)[1].lower()
            allowed_exts = sum(SUPPORTED_MEDIA_TYPES.values(), [])
            if file_ext in allowed_exts:
                tasks.append(download_with_progress(message, "file"))
            else:
                await message.reply(f"File format {file_ext} is not supported.")
        if tasks:
            await asyncio.gather(*tasks)
        else:
            await message.reply("No valid media or URL found in this message.")
    except errors.FloodWait as e:
        from flood_control import handle_flood_wait
        await handle_flood_wait(e, message)
    except Exception as e:
        await message.reply(f"Error processing message: {str(e)}")
