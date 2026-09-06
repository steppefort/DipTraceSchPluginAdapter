"""Build a small Windows x64 GUI executable; requires Zig 0.14.1."""
import argparse
from pathlib import Path
import subprocess
import struct
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--zig',default='zig');a=p.parse_args()
exe=ROOT/'dist/DipTraceSchPluginAdapter.exe';exe.parent.mkdir(exist_ok=True)
subprocess.run([a.zig,'cc','-target','x86_64-windows-gnu','-O2','-s','-municode',str(ROOT/'native/launcher.c'),
                '-Wl,--subsystem,windows','-lshell32','-o',str(exe)],check=True)
b=exe.read_bytes();off=struct.unpack_from('<I',b,0x3c)[0]
assert struct.unpack_from('<H',b,off+4)[0]==0x8664
assert struct.unpack_from('<H',b,off+24+68)[0]==2
print(exe,len(b),'Windows x64 GUI')
