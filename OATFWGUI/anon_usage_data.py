import logging
import hashlib
import subprocess
from pathlib import Path

from platform_check import get_platform, PlatformEnum

log = logging.getLogger('')


def get_uuid() -> str:
    machine_id_fn = {
        PlatformEnum.WINDOWS: get_uuid_windows,
        PlatformEnum.LINUX: get_uuid_linux,
        PlatformEnum.UNKNOWN: lambda: 'unknown',
    }.get(get_platform())
    machine_id_str = machine_id_fn()

    if 'unknown' in machine_id_str.lower():
        uuid_str = machine_id_str  # Keep as human-readable, don't hash
    else:
        uuid_str = hashlib.sha256(machine_id_str.encode()).hexdigest()
    log.debug(f'Got UUID {repr(uuid_str)}')
    return uuid_str


def get_uuid_windows() -> str:
    sub_proc = subprocess.run(
        ['powershell',
         '-Command',
         '(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID',
         ],
        capture_output=True)
    if sub_proc.returncode != 0:
        return 'unknown-windows'
    windows_uuid = sub_proc.stdout.decode('UTF-8')
    return windows_uuid


def get_uuid_linux() -> str:
    id_file = Path('/etc/machine-id')
    if not id_file.exists():
        return 'unknown-linux'

    with open(id_file, 'r') as f:
        machine_id_contents = f.read().strip()
    return machine_id_contents
