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
