"""Small file-based API; independent of any GUI toolkit or BOM implementation."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from .version import __version__

class AdapterError(RuntimeError): pass

def atomic_write(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def json_write(path,value):
    atomic_write(path,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))

def parse_xml(data):
    if len(data)>256*1024*1024:raise AdapterError('Exchange exceeds 256 MiB')
    upper=data.upper().replace(b'\x00',b'')
    if b'<!DOCTYPE' in upper or b'<!ENTITY' in upper:raise AdapterError('DTD/entities are not supported')
    root=ET.fromstring(data,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,insert_pis=True)))
    if root.tag!='Source' or root.get('Type')!='DipTrace-Schematic' or root.find('Schematic') is None:
        raise AdapterError('Expected Source Type="DipTrace-Schematic" with Schematic data')
    return root

def normalized_name(name):
    name=name.strip()
    for left,right in [('<','>'),('%','%')]:
        if name.startswith(left) and name.endswith(right):name=name[1:-1].strip();break
    return name.casefold()

class Context:
    """One captured invocation. New context for each plugin run.

    main(context) may use Tkinter/Qt/etc. Return after UI closes. commit_xml()
    stages a result; the host publishes only after main() returns successfully.
    """
    def __init__(self, request):
        self.request=Path(request).resolve()
        self._data=json.loads(self.request.read_text(encoding='utf-8'))
        if self._data.get('api_version')!=1:raise AdapterError('Unsupported context API')
        self.run_dir=self.request.parent
        self.plugin_dir=Path(self._data['plugin_dir'])
        self.mode=self._data['mode']
        self.plugin_id=self._data['plugin_id']
        self.adapter_version=self._data.get('adapter_version',__version__)
        self.plugin_version=self._data.get('plugin_version')
        self.exchange_path=self.run_dir/'exchange.xml'
        self._staged=None
        self._cancelled=False
        self._selected={}

    def read_xml(self):
        """Read the immutable invocation snapshot, with hash validation."""
        data=self.exchange_path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=self._data['source_sha256']:
            raise AdapterError('Captured input was changed')
        return data

    def document(self):
        """Parse a fresh ElementTree root; unknown nodes are preserved."""
        return parse_xml(self.read_xml())

    @property
    def project_dir(self):
        """ProjectDir from XML, or None. Relative paths resolve beside plugin."""
        raw=(self.document().findtext('./Schematic/Settings/ProjectDir') or '').strip()
        if not raw:return None
        p=Path(raw)
        return p if p.is_absolute() else self.plugin_dir/p

    def environment(self,names):
        """Select case-insensitive inherited names; persist only requested values.

        This reads the child-process environment, not Windows global settings.
        Does not create or edit DipTrace project variables.
        """
        wanted={normalized_name(n) for n in names}
        values={}
        for name,value in os.environ.items():
            key=normalized_name(name)
            if key in wanted:
                if key in values and values[key]!=value:raise AdapterError('Conflicting environment name: '+key)
                values[key]=value
        self._selected.update(values)
        json_write(self.run_dir/'selected_environment.json',self._selected)
        return values

    def commit_xml(self,data):
        """Stage full exchange XML. UI only; respects configured write_scope."""
        if self.mode!='ui':raise AdapterError('job mode cannot return project edits')
        if self._cancelled:raise AdapterError('Invocation already cancelled')
        if isinstance(data,ET.Element):data=ET.tostring(data,encoding='utf-8',xml_declaration=True)
        if not isinstance(data,bytes):raise TypeError('Expected XML bytes or Element')
        from .host import validate_result
        validate_result(self.read_xml(),data,self._data['write_scope'])
        atomic_write(self.run_dir/'result.xml',data)
        self._staged=hashlib.sha256(data).hexdigest()

    def cancel(self):
        """Discard a staged result. Closing a UI without commit is also a no-op."""
        self._cancelled=True;self._staged=None
        (self.run_dir/'result.xml').unlink(missing_ok=True)

    def log(self,message):
        with (self.run_dir/'plugin.log').open('a',encoding='utf-8') as f:f.write(str(message)+'\n')
