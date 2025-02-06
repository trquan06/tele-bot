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
        
        # New statistics
        net_io = psutil.net_io_counters()
        net_sent = net_io.bytes_sent / (1024 * 1024)  # Convert to MB
        net_recv = net_io.bytes_recv / (1024 * 1024)  # Convert to MB        
        return {
            "cpu_usage": f"{cpu_percent}%",
            "ram_usage": f"{ram_percent}% ({ram_used:.1f}GB/{ram_total:.1f}GB)",
            "disk_space": f"{disk_percent}% ({disk_used:.1f}GB/{disk_total:.1f}GB)",
            "network_sent": f"{net_sent:.1f}MB",
            "network_received": f"{net_recv:.1f}MB"
        }
    except Exception as e:
        print(f"Error getting system stats: {e}")
        return {
            "cpu_usage": "N/A",
            "ram_usage": "N/A",
            "disk_space": "N/A",
            "network_sent": "N/A",
            "network_received": "N/A"
        }
