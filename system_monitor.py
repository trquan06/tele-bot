import psutil
import humanize

async def get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    stats = {
        'cpu_usage': f"{cpu_percent}%",
        'ram_usage': f"{memory.percent}% (Used: {humanize.naturalsize(memory.used)}/{humanize.naturalsize(memory.total)})",
        'disk_space': f"Free: {humanize.naturalsize(disk.free)}/{humanize.naturalsize(disk.total)} ({disk.percent}% used)"
    }
    return stats
