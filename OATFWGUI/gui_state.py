import logging
from typing import List, Optional
from collections import namedtuple
from pathlib import Path


log = logging.getLogger('')

FWVersion = namedtuple('FWVersion', ['nice_name', 'url'])
PioEnv = namedtuple('FWVersion', ['nice_name', 'raw_name'])


class LogicState:
    release_list: Optional[List[FWVersion]] = None
    release_idx: Optional[int] = None
    fw_dir: Optional[Path] = None
    pio_envs: List[PioEnv] = []
    pio_env: Optional[str] = None
    config_file_path: Optional[str] = None
    build_success: bool = False
    serial_ports: List[str] = []
    upload_port: Optional[str] = None

    def __setattr__(self, key, val):
        log.debug(f'LogicState updated: {key} {getattr(self, key)} -> {val}')
        super().__setattr__(key, val)
