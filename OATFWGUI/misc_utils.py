import os
import stat
import shutil
import logging
from pathlib import Path
from typing import Callable

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
