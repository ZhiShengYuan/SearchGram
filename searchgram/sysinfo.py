"""
System information collector using psutil.
Provides unified system stats across all Python services.
"""

import psutil
import platform
import time
import re
from datetime import timedelta
from typing import Dict, Any, Optional


def get_cpu_model() -> str:
    """
    Get CPU model name from /proc/cpuinfo on Linux.
    Falls back to platform.processor() on other systems.

    Returns:
        CPU model name or 'Unknown'
    """
    try:
        # Try Linux /proc/cpuinfo first
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.strip().startswith('model name'):
                    # Extract model name after the colon
                    model = line.split(':', 1)[1].strip()
                    return model
    except (FileNotFoundError, IOError):
        pass

    # Fallback to platform.processor()
    processor = platform.processor()
    if processor:
        return processor

    return 'Unknown'


def get_system_info() -> Dict[str, Any]:
    """
    Collect comprehensive system information.

    Returns:
        Dict containing:
        - cpu: CPU usage and load average
        - memory: Memory usage statistics
        - disk: Disk usage for root partition
        - uptime: System uptime
        - os: Operating system information
    """
    # CPU information
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_model = get_cpu_model()
    load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)

    # Memory information
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk information (root partition)
    disk = psutil.disk_usage('/')

    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

    # OS information
    os_info = {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine()
    }

    return {
        'cpu': {
            'model': cpu_model,
            'usage_percent': cpu_percent,
            'count_logical': cpu_count,
            'count_physical': cpu_count_physical,
            'load_average': {
                '1min': round(load_avg[0], 2),
                '5min': round(load_avg[1], 2),
                '15min': round(load_avg[2], 2)
            }
        },
        'memory': {
            'total_gb': round(memory.total / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'percent': memory.percent,
            'swap_total_gb': round(swap.total / (1024**3), 2),
            'swap_used_gb': round(swap.used / (1024**3), 2),
            'swap_percent': swap.percent
        },
        'disk': {
            'total_gb': round(disk.total / (1024**3), 2),
            'used_gb': round(disk.used / (1024**3), 2),
            'free_gb': round(disk.free / (1024**3), 2),
            'percent': disk.percent
        },
        'uptime': {
            'seconds': int(uptime_seconds),
            'formatted': uptime_str
        },
        'os': os_info
    }


def format_system_info(info: Dict[str, Any], service_name: str = "System") -> str:
    """
    Format system info dict into a readable string.

    Args:
        info: System info dict from get_system_info()
        service_name: Name of the service for display

    Returns:
        Formatted string for display
    """
    cpu = info['cpu']
    mem = info['memory']
    disk = info['disk']
    uptime = info['uptime']
    os = info['os']

    lines = [
        f"**{service_name}**",
        f"OS: {os['system']} {os['release']} ({os['machine']})",
        f"Uptime: {uptime['formatted']}",
        "",
        f"CPU: {cpu['model']}",
        f"Usage: {cpu['usage_percent']}% | {cpu['count_logical']} cores ({cpu['count_physical']} physical)",
        f"Load: {cpu['load_average']['1min']} / {cpu['load_average']['5min']} / {cpu['load_average']['15min']} (1/5/15min)",
        "",
        f"Memory: {mem['used_gb']}/{mem['total_gb']} GB ({mem['percent']}%)",
        f"Available: {mem['available_gb']} GB",
        f"Swap: {mem['swap_used_gb']}/{mem['swap_total_gb']} GB ({mem['swap_percent']}%)",
        "",
        f"Disk (/): {disk['used_gb']}/{disk['total_gb']} GB ({disk['percent']}%)",
        f"Free: {disk['free_gb']} GB"
    ]

    return "\n".join(lines)


if __name__ == '__main__':
    # Test the module
    info = get_system_info()
    print(format_system_info(info, "Test System"))
