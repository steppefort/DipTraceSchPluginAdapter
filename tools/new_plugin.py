"""Create a local job/UI example, with the current checked-out adapter."""
import argparse
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from vendor_adapter import install
ROOT=Path(__file__).resolve().parents[1]

def create(destination,name,mode):
    if mode not in ('job','ui'):raise ValueError('Unknown mode')
    if destination.exists():raise FileExistsError('Destination already exists')
    # Name validation is shared with vendoring, before business files are written.
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name):raise ValueError('Invalid plugin name')
    destination.mkdir(parents=True)
    shutil.copy2(ROOT/'examples'/mode/'plugin.py',destination/'plugin.py')
    (destination/'adapter.ini').write_text(f'''[adapter]
api_version = 1
plugin_id = {name}
mode = {mode}
write_scope = sheet_settings
capture_dir =

[python]
; Or an absolute path to pythonw.exe, without quotes.
executable = pyw.exe

[plugin]
entry = plugin.py
''',encoding='utf-8')
    source=ET.Element('Source',Type='DipTrace_Schematic_Plugin',Name=name,ExeFile=name+'.exe',Hint='DipTraceSchPluginAdapter example')
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
    a=p.parse_args();print(create(a.destination,a.name,a.mode))
