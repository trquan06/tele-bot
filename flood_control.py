import asyncio
from datetime import datetime, timedelta

# Global dictionary to track flood wait status per chat
flood_wait_status = {}

# Global dictionary to track rate limiting status per chat
rate_limit_status = {}
async def handle_flood_wait(error, message):
    """
    Handles Telegram FloodWait errors with notifications.
    """
    try:
        wait_time = error.value
        chat_id = message.chat.id
        end_time = datetime.now() + timedelta(seconds=wait_time)
        
        # Store flood wait status
        flood_wait_status[chat_id] = {
            'end_time': end_time,
            'wait_time': wait_time,
            'start_time': datetime.now()
        }
        
        status_message = await message.reply(
            f"⚠️ FloodWait activated!\n"
            f"⏳ Please wait {wait_time} seconds.\n"
            f"⏰ Resuming at: {end_time.strftime('%H:%M:%S')}"
        )
        
        # Update the countdown every second
        while datetime.now() < end_time:
            remaining = (end_time - datetime.now()).total_seconds()
            await asyncio.sleep(1)
            # Optionally, update every 10 seconds
            if int(remaining) % 10 == 0:
                await status_message.edit_text(
                    f"⚠️ FloodWait active!\n"
                    f"⏳ Remaining: {int(remaining)} seconds\n"
                    f"⏰ Resuming at: {end_time.strftime('%H:%M:%S')}"
                )
        
        # Remove flood wait status
        flood_wait_status.pop(chat_id, None)
        await status_message.edit_text("✅ FloodWait period ended. Resuming operations.")
        
    except Exception as e:
        print(f"Error in flood wait handler: {e}")
        flood_wait_status.pop(message.chat.id, None)

async def check_flood_wait_status(chat_id):
    """
    Checks if a chat is under a flood wait.
    Returns a tuple (is_waiting, remaining_time).
    """
    if chat_id in flood_wait_status:
        remaining = (flood_wait_status[chat_id]['end_time'] - datetime.now()).total_seconds()
        if remaining > 0:
            return True, remaining
        else:
            flood_wait_status.pop(chat_id, None)
    return False, 0

async def rate_limit(chat_id, limit=5, period=60):
    """
    Implements rate limiting to prevent API abuse.
    """
    now = datetime.now()
    if chat_id not in rate_limit_status:
        rate_limit_status[chat_id] = []

    # Remove timestamps older than the period
    rate_limit_status[chat_id] = [timestamp for timestamp in rate_limit_status[chat_id] if (now - timestamp).total_seconds() < period]

    if len(rate_limit_status[chat_id]) >= limit:
        wait_time = period - (now - rate_limit_status[chat_id][0]).total_seconds()
        raise Exception(f"Rate limit exceeded. Try again in {int(wait_time)} seconds.")

    rate_limit_status[chat_id].append(now)
