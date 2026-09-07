"""Package a validated adapter build as a versioned source/runtime ZIP."""
import argparse
import hashlib
from pathlib import Path
import zipfile
from versioning import ROOT, sync

EXCLUDED = {'.git', '__pycache__', '.venv', '.pytest_cache', 'build', 'captures'}

def package(output_dir):
    info = sync(check=True)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    def include(path):
        relative = path.relative_to(ROOT)
        return (path.is_file() and not any(part in EXCLUDED for part in relative.parts)
                and not path.is_relative_to(output_dir)
                and path.suffix not in ('.pyc', '.pyo', '.log', '.zip')
                and path.name not in ('SHA256SUMS.txt', 'PACKAGE_SHA256SUMS.txt'))
    files = sorted(p for p in ROOT.rglob('*') if include(p))
    checksums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n'
                        for p in files)
    for name in ('SHA256SUMS.txt', 'PACKAGE_SHA256SUMS.txt'):
        path = ROOT/name
        path.write_text(checksums, encoding='utf-8')
        files.append(path)
    archive_path = output_dir/f'DipTraceSchPluginAdapter-{info["version"]}.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, Path('DipTraceSchPluginAdapter')/path.relative_to(ROOT))
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None: raise ValueError('Corrupted release archive')
        for line in checksums.splitlines():
            digest, name = line.split('  ', 1)
            if hashlib.sha256(archive.read('DipTraceSchPluginAdapter/'+name)).hexdigest() != digest:
                raise ValueError(f'Archive hash mismatch: {name}')
    print(archive_path)
    return archive_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'build/releases')
    package(parser.parse_args().output_dir)
