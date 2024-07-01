import logging
import hashlib
import subprocess
import json
import requests
from pathlib import Path
from typing import Tuple
from functools import lru_cache

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtGui import QFont
import pygments
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter

from platform_check import get_platform, PlatformEnum
from gui_state import LogicState
from misc_utils import decode_bytes

log = logging.getLogger('')


class AnonStatsDialog(QDialog):
    def __init__(self, logic_state: LogicState, parent=None):
        super().__init__(parent)

        self.setWindowTitle('What statistics will be uploaded?')

        QBtn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        usage_stats_html = dict_to_html(create_anon_stats(logic_state))

        wLbl_1 = QLabel('''
These statistics are invaluable for us developers on figuring out what our users are actually
building, so we can figure out where to put our (limited!) time working towards improving.
After a successful OAT firmware upload the following data will be sent to our statistics server:
'''.replace('\n', ' '))
        wLbl_1.setWordWrap(True)
        wLbl_1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.wBtn_show_hide = QPushButton('▶Click to expand:')
        self.wBtn_show_hide.setStyleSheet('QPushButton { color: #0074cc; background-color: transparent; border: 0px; }')
        self.wBtn_show_hide.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wBtn_show_hide.clicked.connect(self.show_hide_html)

        self.wTxt_html = QPlainTextEdit()
        self.wTxt_html.setReadOnly(True)
        self.wTxt_html.appendHtml(f'{usage_stats_html}')
        self.wTxt_html.setMinimumSize(500, 250)
        self.wTxt_html.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.wTxt_html.hide()

        wLbl_2 = QLabel('''
(the data might not fully be populated yet, you need to progress through the GUI steps first)
'''.replace('\n', ' '))
        italic_font = QFont()
        italic_font.setItalic(True)
        wLbl_2.setFont(italic_font)
        wLbl_2.setWordWrap(True)
        wLbl_2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.layout = QVBoxLayout()
        self.layout.addWidget(wLbl_1)
        self.layout.addWidget(self.wBtn_show_hide)
        self.layout.addWidget(self.wTxt_html)
        self.layout.addWidget(wLbl_2)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def show_hide_html(self):
        show_hide_text = self.wBtn_show_hide.text()
        if self.wTxt_html.isVisible():
            self.wTxt_html.hide()
            show_hide_text = show_hide_text.replace('▼', '▶')
        else:
            self.wTxt_html.show()
            show_hide_text = show_hide_text.replace('▶', '▼')
        self.wBtn_show_hide.setText(show_hide_text)


def dict_to_html(in_dict: dict) -> str:
    json_str = json.dumps(in_dict, indent=4, sort_keys=True)
    json_lexer = JsonLexer()
    html_formatter = HtmlFormatter(noclasses=True, nobackground=True)
    data_html = pygments.highlight(json_str, json_lexer, html_formatter)
    return data_html


def create_anon_stats(logic_state: LogicState) -> dict:
    if logic_state.release_idx is not None:
        release_name = logic_state.release_list[logic_state.release_idx].nice_name
    else:
        release_name = None

    if logic_state.config_file_path is not None:
        with open(Path(logic_state.config_file_path).resolve(), 'r') as fp:
            config_file = fp.read()
    else:
        config_file = None

    # Catch-all for these so we never crash when getting anon-stats
    try:
        computer_uuid = get_computer_uuid()
    except Exception as e:
        log.error(f'get_uuid exception: {e}')
        computer_uuid = 'unknown'
    try:
        approx_lat, approx_lon = get_approx_location()
    except Exception as e:
        log.error(f'get_approx_location exception: {e}')
        approx_lat, approx_lon = None, None

    stats = {
        'host_uuid': computer_uuid,
        'pio_env': logic_state.pio_env,
        'release_version': release_name,
        'config_file': config_file,
        'approx_lat': approx_lat,
        'approx_lon': approx_lon,
    }
    return stats


def upload_anon_stats(anon_stats: dict) -> bool:
    analytics_url = 'http://config.cloud.openastrotech.com/api/v1/config/'
    log.info(f'Uploading statistics to {analytics_url}')
    try:
        r = requests.post(analytics_url, json=anon_stats, timeout=2.0)
    except Exception as e:
        log.error(f'Failed to POST statistics: {e}')
        return False
    if r.status_code != requests.codes.ok:
        log.error(f'Failed to POST statistics: {r.status_code} {r.reason} {r.text}')
        return False
    return True


@lru_cache(maxsize=1)
def get_computer_uuid() -> str:
    machine_id_fn = {
        PlatformEnum.WINDOWS: get_uuid_windows,
        PlatformEnum.LINUX: get_uuid_linux,
        PlatformEnum.MACOS: get_uuid_macos,
        PlatformEnum.UNKNOWN: lambda: 'unknown platform',
    }.get(get_platform(), lambda: 'unknown, unhandled platform')
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
    windows_uuid = decode_bytes(sub_proc.stdout)
    return windows_uuid


def get_uuid_linux() -> str:
    id_file = Path('/etc/machine-id')
    if not id_file.exists():
        return 'unknown-linux'

    with open(id_file, 'r') as f:
        machine_id_contents = f.read().strip()
    return machine_id_contents


def get_uuid_macos() -> str:
    sub_proc = subprocess.run(
        ['ioreg',
         '-rd1',
         '-c',
         'IOPlatformExpertDevice',
         ],
        capture_output=True)
    if sub_proc.returncode != 0:
        return 'unknown-macos'
    ioreg_output = sub_proc.stdout.decode('UTF-8')
    return windows_uuid


def to_nearest_half(num: float) -> float:
    return round(num * 2, 0) / 2


@lru_cache(maxsize=1)
def get_approx_location() -> Tuple[float, float]:
    geo_ip_url = 'https://ipinfo.io/loc'
    response = requests.get(geo_ip_url, timeout=2.0)
    resp_str = decode_bytes(response.content).strip()
    lat_str, lon_str = resp_str.split(',')
    lat_approx = to_nearest_half(float(lat_str))
    lon_approx = to_nearest_half(float(lon_str))
    return lat_approx, lon_approx
