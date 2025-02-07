import time
from datetime import timedelta
import humanize

async def progress_callback(current, total, status_message, start_time, media_type):
    try:
        if total is None:
            return
            
        elapsed_time = time.time() - start_time
        if elapsed_time == 0:
            return
            
        speed = current / elapsed_time
        percentage = (current * 100) / total
        estimated_total_time = elapsed_time * (total / current if current > 0 else 0)
        
        progress_text = (
            f"📥 Downloading {media_type}...\n"
            f"▪️ Size: {current/(1024*1024):.1f}/{total/(1024*1024):.1f} MB\n"
            f"▪️ Progress: {percentage:.1f}%\n"
            f"▪️ Speed: {speed/1024:.1f} KB/s\n"
            f"▪️ ETA: {time.strftime('%H:%M:%S', time.gmtime(estimated_total_time))}"
        )
        
        # Cập nhật message mỗi 2 giây hoặc khi hoàn thành
        if (time.time() - start_time) % 2 < 0.1 or current == total:
            await status_message.edit_text(progress_text)
            
    except Exception as e:
        logger.error(f"Error in progress callback: {str(e)}")
