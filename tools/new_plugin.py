"""Create a local job/UI example, with the current checked-out adapter."""
import argparse
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from vendor_adapter import install
from versioning import read_info
ROOT=Path(__file__).resolve().parents[1]

def create(destination,name,mode,plugin_version=None):
    if mode not in ('job','ui'):raise ValueError('Unknown mode')
    if destination.exists():raise FileExistsError('Destination already exists')
    # Name validation is shared with vendoring, before business files are written.
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name):raise ValueError('Invalid plugin name')
    if plugin_version is not None and not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',plugin_version):
        raise ValueError('Plugin version must be MAJOR.MINOR.PATCH')
    adapter_info=read_info(ROOT)
    destination.mkdir(parents=True)
    shutil.copy2(ROOT/'examples'/mode/'plugin.py',destination/'plugin.py')
    (destination/'adapter.ini').write_text(f'''[adapter]
api_version = {adapter_info["api_version"]}
plugin_id = {name}
mode = {mode}
write_scope = sheet_settings
capture_dir =

[python]
; Or an absolute path to pythonw.exe, without quotes.
executable = pyw.exe

[plugin]
entry = plugin.py
version = {plugin_version or ''}
''',encoding='utf-8')
    display_name=f'{name} {plugin_version}' if plugin_version else name
    source=ET.Element('Source',Type='DipTrace_Schematic_Plugin',Name=display_name,ExeFile=name+'.exe',Hint='DipTraceSchPluginAdapter example')
    settings=ET.SubElement(source,'Settings')
    tags={'ExpMode':'All','ImpMode':'None' if mode=='job' else 'All',
          'Comp':'All','Net':'All','Shape':'All','Bus':'All','Table':'All','BusConnectors':'All','Diff':'All',
          'Dim':'None','Board':'None','Trace':'None','Stamp':'Yes','Patterns':'Yes'}
    for key,value in tags.items():ET.SubElement(settings,key).text=value
    ET.indent(source)
    (destination/'settings.xml').write_bytes(ET.tostring(source,encoding='utf-8',xml_declaration=True))
    try:revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],stderr=subprocess.DEVNULL,text=True).strip()
    except subprocess.CalledProcessError:revision='local-development'
    install(ROOT,destination,name+'.exe','local-checkout',revision)
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);p.add_argument('--name',required=True);p.add_argument('--mode',choices=['job','ui'],required=True)
    p.add_argument('--plugin-version',help='Independent plugin version, shown in the DipTrace menu')
    a=p.parse_args();print(create(a.destination,a.name,a.mode,a.plugin_version))
