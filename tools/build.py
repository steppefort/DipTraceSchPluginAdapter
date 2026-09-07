"""Build the Windows x64 launcher and its version resources with Zig 0.14.1."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from versioning import ROOT, sync

def build(zig):
    info = sync()
    version = info['version']
    work = ROOT/'build/native'
    work.mkdir(parents=True, exist_ok=True)
    resource = work/'version.rc'
    numeric = version.replace('.', ',') + ',0'
    resource.write_text(f'''1 VERSIONINFO
FILEVERSION {numeric}
PRODUCTVERSION {numeric}
FILEFLAGSMASK 0x3fL
FILEFLAGS 0x0L
FILEOS 0x40004L
FILETYPE 0x1L
FILESUBTYPE 0x0L
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904b0"
  BEGIN
   VALUE "FileDescription", "DipTrace Schematic Python Plugin Adapter"
   VALUE "FileVersion", "{version}"
   VALUE "InternalName", "DipTraceSchPluginAdapter"
   VALUE "OriginalFilename", "DipTraceSchPluginAdapter.exe"
   VALUE "ProductName", "DipTraceSchPluginAdapter"
   VALUE "ProductVersion", "{version}"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x0409, 1200
 END
END
''', encoding='utf-8')
    compiled = work/'version.res'
    subprocess.run([zig, 'rc', '/fo', str(compiled), '--', str(resource)], check=True)
    exe = ROOT/'dist/DipTraceSchPluginAdapter.exe'
    exe.parent.mkdir(exist_ok=True)
    temporary = work/'DipTraceSchPluginAdapter.exe'
    subprocess.run([zig, 'cc', '-target', 'x86_64-windows-gnu', '-O2', '-s', '-municode',
                    str(ROOT/'native/launcher.c'), str(compiled), '-Wl,--subsystem,windows',
                    '-lshell32', '-o', str(temporary)], check=True)
    data = temporary.read_bytes()
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    assert struct.unpack_from('<H', data, offset+4)[0] == 0x8664
    assert struct.unpack_from('<H', data, offset+24+68)[0] == 2
    exe.write_bytes(data)
    info.update(built_version=version, built_api_version=info['api_version'],
                build='Zig '+subprocess.check_output([zig, 'version'], text=True).strip()+
                      '; x86_64-windows-gnu; GUI subsystem',
                exe_sha256=hashlib.sha256(data).hexdigest(), exe_bytes=len(data),
                native_source_sha256=hashlib.sha256((ROOT/'native/launcher.c').read_bytes()).hexdigest())
    (ROOT/'build_info.json').write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
    print(f'{exe} ({version}, API {info["api_version"]}), {len(data)} bytes')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig', default='zig')
    build(parser.parse_args().zig)
