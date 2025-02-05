import time
from datetime import timedelta
import humanize

async def progress_callback(current, total, message, start_time, file_type):
    """
    Provides progress updates for downloads.
    """
    try:
        if total == 0:
            return

        now = time.time()
        elapsed = now - start_time

        # Update only if more than 2 seconds elapsed or download finished
        if elapsed > 2 or current == total:
            percentage = (current / total) * 100
            speed = current / elapsed if elapsed > 0 else 0

            # Estimate remaining time
            eta = (total - current) / speed if speed > 0 else 0

            progress_text = (
                f"Downloading {file_type}: {percentage:.1f}%\n"
                f"Downloaded: {humanize.naturalsize(current)}/{humanize.naturalsize(total)}\n"
                f"Speed: {humanize.naturalsize(speed)}/s\n"
                f"ETA: {str(timedelta(seconds=int(eta)))}"
            )
            await message.edit_text(progress_text)
    except Exception:
        # If editing fails, just skip updating
        pass
