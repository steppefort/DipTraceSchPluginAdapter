"""Generate version metadata from the repository's build_info.json."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def read_info(root=ROOT):
    info = json.loads((root / 'build_info.json').read_text(encoding='utf-8'))
    version = info['version']
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('version must be a stable MAJOR.MINOR.PATCH release')
    if any(int(n) > 65535 for n in version.split('.')):
        raise ValueError('Version components must fit Windows VERSIONINFO')
    if type(info['api_version']) is not int or info['api_version'] < 1:
        raise ValueError('api_version must be a positive integer')
    return info

def sync(root=ROOT, check=False):
    info = read_info(root)
    version, api = info['version'], info['api_version']
    metadata = json.dumps({'version': version, 'api_version': api}, indent=2) + '\n'
    header = ('/* Generated from build_info.json by tools/versioning.py. */\n'
              '#pragma once\n'
              f'#define ADAPTER_VERSION_W L"{version}"\n'
              f'#define ADAPTER_API_W L"{api}"\n'
              '#define ADAPTER_TITLE_W L"DipTraceSchPluginAdapter " ADAPTER_VERSION_W\n')
    outputs = {root/'python/diptrace_adapter/build_info.json': metadata,
               root/'native/version.h': header}
    for name, prefix, license_text in [('README.md', 'Version', '**MIT** license. An independent community project.'),
                                       ('README_UA.md', 'Версія', 'ліцензія **MIT**. Незалежний проєкт спільноти.')]:
        path = root/name
        content = path.read_text(encoding='utf-8')
        previous = re.search(r'^'+prefix+r' \*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*',content,re.MULTILINE)
        if previous and previous[1] != version:
            # Keep current-release archive names, tag commands and examples in sync.
            content = re.sub(r'(?<![0-9])'+re.escape(previous[1])+r'(?![0-9])',version,content)
        content, count = re.subn(r'^'+prefix+r' \*\*[^\n]+$',
                                 f'{prefix} **{version}**, API **{api}**, {license_text}',
                                 content, count=1, flags=re.MULTILINE)
        if count != 1: raise ValueError(f'Missing version line in {name}')
        outputs[path] = content
    for path, text in outputs.items():
        if check:
            if not path.exists() or path.read_text(encoding='utf-8') != text:
                raise ValueError(f'Stale version metadata: {path.relative_to(root)}; run tools/build.py')
        else:
            path.write_text(text, encoding='utf-8')
    if check:
        binary = root/'dist/DipTraceSchPluginAdapter.exe'
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        if digest != info.get('exe_sha256') or binary.stat().st_size != info.get('exe_bytes'):
            raise ValueError('EXE does not match build_info.json; rebuild it')
        if hashlib.sha256((root/'native/launcher.c').read_bytes()).hexdigest() != info.get('native_source_sha256'):
            raise ValueError('Native source changed after build; rebuild it')
        if info.get('built_version') != version or info.get('built_api_version') != api:
            raise ValueError('EXE was built for another version; rebuild it')
    return info

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    info = sync(check=args.check)
    print(f"DipTraceSchPluginAdapter {info['version']}, API {info['api_version']}")
