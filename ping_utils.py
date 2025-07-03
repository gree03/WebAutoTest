import asyncio
import os
from typing import List, Dict, Tuple

async def _ping(ip: str) -> Tuple[str, bool]:
    """Ping an IP address once. Return (ip, reachable)."""
    if os.name == 'nt':
        cmd = ['ping', '-n', '1', ip]
    else:
        cmd = ['ping', '-c', '1', '-W', '1', ip]
    proc = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL)
    await proc.communicate()
    return ip, proc.returncode == 0

async def _check_all(ips: List[str]) -> Dict[str, bool]:
    coros = [_ping(ip) for ip in ips]
    results = await asyncio.gather(*coros)
    return {ip: ok for ip, ok in results}

def check_ips(ips: List[str]) -> Dict[str, bool]:
    """Synchronously check reachability of IPs using async ping."""
    if not ips:
        return {}
    return asyncio.run(_check_all(ips))


def filter_reachable_devices(devices: List[dict]) -> Tuple[List[dict], List[str]]:
    """Return devices reachable by ping and list of warning messages."""
    ips = []
    for d in devices:
        ip = d.get('IP_CAMERA', '')
        ip = ip.split(':')[0]
        if ip and ip not in ips:
            ips.append(ip)
    results = check_ips(ips)
    reachable = {ip for ip, ok in results.items() if ok}
    warnings = [f"\u274c \"Домофон {ip} недоступен \u2014 исключён из теста\"" for ip, ok in results.items() if not ok]
    filtered = [d for d in devices if d.get('IP_CAMERA', '').split(':')[0] in reachable]
    return filtered, warnings

