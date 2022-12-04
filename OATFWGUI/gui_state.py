import logging
from typing import NamedTuple, List, Optional
from pathlib import Path


log = logging.getLogger('')


class FWVersion(NamedTuple):
    nice_name: str
    url: str


class PioEnv(NamedTuple):
    nice_name: str
    raw_name: str


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
