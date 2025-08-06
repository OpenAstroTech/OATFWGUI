import os
import stat
import shutil
import logging
from pathlib import Path
from typing import Callable
from platform_check import get_platform, PlatformEnum

log = logging.getLogger('')


def delete_directory(dir_to_delete: Path):
    def remove_readonly(func: Callable, path, excinfo):
        # Windows has a problem with deleting some git files
        log.debug(f'Problem removing {path}, attempting to make writable')
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(dir_to_delete, onerror=remove_readonly)


def decode_bytes(byte_string: bytes) -> str:
    # Just to consolidate all text decoding and make sure they're all the same
    return byte_string.decode('utf-8', errors='backslashreplace')

def get_env_var(env_var) -> str:
    if get_platform() == PlatformEnum.WINDOWS:
        # Use %MY_PATH% syntax
        return f'%{env_var}%'
    else:
        # Use $MY_PATH syntax
        cmd = f'${env_var}' 