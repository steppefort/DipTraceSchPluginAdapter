"""Vendor the runtime from a pinned root repository commit. Never runs at startup."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

def install(root,destination,exe_name,repository,revision):
    root=Path(root);destination=Path(destination)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.exe',exe_name):raise ValueError('Use an ASCII exe basename')
    binary=root/'dist/DipTraceSchPluginAdapter.exe'
    if not binary.is_file():raise FileNotFoundError('Pinned source needs dist/DipTraceSchPluginAdapter.exe')
    info=json.loads((root/'build_info.json').read_text(encoding='utf-8'))
    if 'built_version' in info:
        snapshot=json.loads((root/'python/diptrace_adapter/build_info.json').read_text(encoding='utf-8'))
        if (info['version']!=info['built_version'] or info['api_version']!=info['built_api_version']
            or snapshot!={'version':info['version'],'api_version':info['api_version']}
            or hashlib.sha256(binary.read_bytes()).hexdigest()!=info['exe_sha256']):
            raise ValueError('Adapter build metadata is stale; rebuild the adapter before vendoring')
    # Prepare runtime before replacing an old dependency; business files untouched.
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temp:
        staged=Path(temp)/'.adapter'
        shutil.copytree(root/'python',staged,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for notice in ('LICENSE','THIRD_PARTY.md'):
            if (root/notice).exists():shutil.copy2(root/notice,staged/notice)
        if (root/'third_party').exists():shutil.copytree(root/'third_party',staged/'third_party')
        runtime=destination/'.adapter'
        backup=destination/'.adapter.previous'
        if backup.exists():shutil.rmtree(backup)
        if runtime.exists():runtime.rename(backup)
        try:staged.rename(runtime)
        except Exception:
            if backup.exists():backup.rename(runtime)
            raise
        shutil.copy2(binary,destination/exe_name)
    files=[destination/exe_name,*sorted(p for p in (destination/'.adapter').rglob('*') if p.is_file())]
    lock={'adapter':'DipTraceSchPluginAdapter','adapter_version':info['version'],
          'api_version':info['api_version'],'repository':repository,'commit':revision,
          'files':{str(p.relative_to(destination)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (destination/'adapter.lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    return lock

def fetch(repository,revision,destination,exe_name):
    if not re.fullmatch(r'[0-9a-fA-F]{40}',revision):raise ValueError('Pin a full 40-character commit SHA, not a moving branch')
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run(['git','init','--quiet',temp],check=True)
        subprocess.run(['git','-C',temp,'fetch','--quiet','--depth=1','--',repository,revision],check=True)
        actual=subprocess.check_output(['git','-C',temp,'rev-parse','FETCH_HEAD'],text=True).strip()
        if actual.lower()!=revision.lower():raise ValueError('Fetched commit mismatch')
        subprocess.run(['git','-C',temp,'checkout','--quiet','--detach',actual],check=True)
        return install(temp,destination,exe_name,repository,actual)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit',required=True)
    p.add_argument('--dest',type=Path,required=True);p.add_argument('--exe',required=True);a=p.parse_args()
    fetch(a.repo,a.commit,a.dest,a.exe)
