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


def get_arm_cpu_name(cpu_part: str) -> str:
    """
    Map ARM CPU part numbers to human-readable names.

    Args:
        cpu_part: CPU part number (e.g., '0xd05')

    Returns:
        CPU core name or the part number if unknown
    """
    arm_cpu_map = {
        '0xd03': 'Cortex-A53',
        '0xd04': 'Cortex-A35',
        '0xd05': 'Cortex-A55',
        '0xd07': 'Cortex-A57',
        '0xd08': 'Cortex-A72',
        '0xd09': 'Cortex-A73',
        '0xd0a': 'Cortex-A75',
        '0xd0b': 'Cortex-A76',
        '0xd0c': 'Neoverse N1',
        '0xd0d': 'Cortex-A77',
        '0xd0e': 'Cortex-A76AE',
        '0xd40': 'Neoverse V1',
        '0xd41': 'Cortex-A78',
        '0xd42': 'Cortex-A78AE',
        '0xd44': 'Cortex-X1',
        '0xd46': 'Cortex-A510',
        '0xd47': 'Cortex-A710',
        '0xd48': 'Cortex-X2',
        '0xd49': 'Neoverse N2',
        '0xd4a': 'Neoverse E1',
        '0xd4b': 'Cortex-A78C',
        '0xd4c': 'Cortex-X1C',
        '0xd4d': 'Cortex-A715',
        '0xd4e': 'Cortex-X3',
    }
    return arm_cpu_map.get(cpu_part.lower(), cpu_part)


def get_cpu_model() -> str:
    """
    Get CPU model name from /proc/cpuinfo on Linux (supports x86/x64 and ARM).
    Falls back to platform.processor() on other systems.

    Returns:
        CPU model name or 'Unknown'
    """
    try:
        # Try Linux /proc/cpuinfo first
        # Different architectures use different field names:
        # - x86/x64: "model name"
        # - ARM: Need to parse CPU implementer/part and check device tree
        cpu_info = {}
        cpu_parts = []  # Store all CPU part numbers for ARM big.LITTLE configs

        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    # Store first occurrence of each field
                    if key not in cpu_info:
                        cpu_info[key] = value

                    # Collect all CPU part numbers for ARM
                    if key == 'cpu part':
                        if value not in cpu_parts:
                            cpu_parts.append(value)

        # 1. x86/x64: "model name" (e.g., "Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz")
        if 'model name' in cpu_info and cpu_info['model name']:
            return cpu_info['model name']

        # 2. ARM: Try device tree model and compatible (most accurate for SBC/embedded)
        dt_model = None
        dt_soc = None

        # Read model (e.g., "FriendlyElec NanoPi R6S")
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as f:
                dt_model = f.read().strip('\x00').strip()
        except (FileNotFoundError, IOError):
            pass

        # Read compatible strings (e.g., "friendlyelec,nanopi-r6s\0rockchip,rk3588s\0")
        try:
            with open('/sys/firmware/devicetree/base/compatible', 'rb') as f:
                compatible = f.read().decode('utf-8', errors='ignore')
                # Split by null bytes and parse
                parts = [s for s in compatible.split('\x00') if s]

                # Look for SoC vendor strings (rockchip, amlogic, broadcom, etc.)
                for part in parts:
                    if ',' in part:
                        vendor, model = part.split(',', 1)
                        vendor_lower = vendor.lower()
                        # Common SoC vendors
                        if vendor_lower in ['rockchip', 'amlogic', 'broadcom', 'allwinner',
                                           'mediatek', 'qualcomm', 'samsung', 'nvidia']:
                            # Capitalize vendor and uppercase model
                            dt_soc = f"{vendor.capitalize()} {model.upper()}"
                            break
        except (FileNotFoundError, IOError, UnicodeDecodeError):
            pass

        # Combine model and SoC info
        if dt_model and dt_soc:
            return f"{dt_model} ({dt_soc})"
        elif dt_model:
            return dt_model
        elif dt_soc:
            return dt_soc

        # 3. ARM: "Hardware" field (e.g., "BCM2835" on older Raspberry Pi)
        if 'hardware' in cpu_info and cpu_info['hardware']:
            hardware = cpu_info['hardware']
            # Combine with Model if available for more detail
            if 'model' in cpu_info and cpu_info['model']:
                return f"{cpu_info['model']} ({hardware})"
            return hardware

        # 4. ARM: "Model" field (e.g., "Raspberry Pi 4 Model B Rev 1.2")
        if 'model' in cpu_info and cpu_info['model']:
            return cpu_info['model']

        # 5. ARM: Parse CPU implementer and part numbers
        if cpu_parts and 'cpu implementer' in cpu_info:
            implementer = cpu_info['cpu implementer']

            # ARM Ltd implementer (0x41)
            if implementer == '0x41':
                # Map part numbers to names and handle big.LITTLE
                cpu_names = [get_arm_cpu_name(part) for part in cpu_parts]
                unique_names = []
                for name in cpu_names:
                    if name not in unique_names:
                        unique_names.append(name)

                if len(unique_names) == 1:
                    return f"ARM {unique_names[0]}"
                else:
                    # big.LITTLE configuration
                    return f"ARM {' + '.join(unique_names)}"

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
