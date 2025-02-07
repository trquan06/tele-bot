from pyrogram import errors
import asyncio
import logging

logger = logging.getLogger(__name__)

async def handle_download_error(e, message, retry_count=0, max_retries=3):
    """Handle different types of download errors"""
    if isinstance(e, errors.FloodWait):
        if retry_count < max_retries:
            wait_time = e.value
            await message.reply(f"FloodWait detected. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            return True
        else:
            await message.reply("Maximum retry attempts reached for FloodWait.")
            return False
            
    elif isinstance(e, asyncio.TimeoutError):
        await message.reply("Download timed out. Please try again.")
        return False
        
    elif isinstance(e, errors.FilePartMissing):
        await message.reply("File part missing. Please try downloading again.")
        return False
        
    else:
        logger.error(f"Download error: {str(e)}")
        await message.reply(f"Error during download: {str(e)}")
        return False
