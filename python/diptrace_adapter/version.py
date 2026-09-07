"""Installed version snapshot generated from the repository build_info.json."""
import json
from pathlib import Path

_info = json.loads(Path(__file__).with_name('build_info.json').read_text(encoding='utf-8'))
__version__ = _info['version']
API_VERSION = _info['api_version']
