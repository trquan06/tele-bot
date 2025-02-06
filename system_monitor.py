import psutil
import os
from config import BASE_DOWNLOAD_FOLDER

async def get_system_stats():
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # RAM usage
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_used = ram.used / (1024 * 1024 * 1024)  # Convert to GB
        ram_total = ram.total / (1024 * 1024 * 1024)  # Convert to GB
        
        # Disk usage for download folder
        disk = psutil.disk_usage(BASE_DOWNLOAD_FOLDER)
        disk_percent = disk.percent
        disk_used = disk.used / (1024 * 1024 * 1024)  # Convert to GB
        disk_total = disk.total / (1024 * 1024 * 1024)  # Convert to GB
        
        return {
            "cpu_usage": f"{cpu_percent}%",
            "ram_usage": f"{ram_percent}% ({ram_used:.1f}GB/{ram_total:.1f}GB)",
            "disk_space": f"{disk_percent}% ({disk_used:.1f}GB/{disk_total:.1f}GB)"
        }
    except Exception as e:
        print(f"Error getting system stats: {e}")
        return {
            "cpu_usage": "N/A",
            "ram_usage": "N/A",
            "disk_space": "N/A"
        }
