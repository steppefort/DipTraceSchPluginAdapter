"""Transport lifecycle, process launch and transactional return to DipTrace."""
from __future__ import annotations
import argparse
import configparser
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import traceback
import uuid
import xml.etree.ElementTree as ET
from .api import AdapterError, Context, atomic_write, json_write, parse_xml
from .version import __version__, API_VERSION


def read_config(path):
    path=Path(path).resolve();raw=path.read_bytes()
    c=configparser.ConfigParser(interpolation=None)
    c.read_string(raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'))
    if c.getint('adapter','api_version',fallback=1)!=1:raise AdapterError('Unsupported API version')
    mode=c.get('adapter','mode',fallback='job')
    if mode not in ('job','ui'):raise AdapterError('mode must be job or ui')
    plugin_id=c.get('adapter','plugin_id',fallback=path.parent.name)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',plugin_id):raise AdapterError('Invalid plugin_id')
    scope=c.get('adapter','write_scope',fallback='sheet_settings')
    if scope not in ('sheet_settings','full'):raise AdapterError('Invalid write_scope')
    entry=(path.parent/c.get('plugin','entry',fallback='plugin.py')).resolve()
    if not entry.is_file():raise AdapterError('Plugin entry missing: '+str(entry))
    settings=parse_settings(path.parent/'settings.xml')
    if mode=='job' and settings['ImpMode']!='None':raise AdapterError('job requires ImpMode=None')
    # Full exchange round trip: no partial list replacement is allowed here.
    if mode=='ui' and (settings['ExpMode']!='All' or settings['ImpMode']!='All'):
        raise AdapterError('ui API v1 requires ExpMode=All and ImpMode=All')
    return c,dict(api_version=API_VERSION,adapter_version=__version__,
                  plugin_version=c.get('plugin','version',fallback='').strip() or None,
                  mode=mode,plugin_id=plugin_id,write_scope=scope,
                  plugin_dir=str(path.parent),entry=str(entry),config_path=str(path),settings=settings)


def parse_settings(path):
    root=ET.parse(path).getroot()
    if root.tag!='Source' or root.get('Type')!='DipTrace_Schematic_Plugin':raise AdapterError('Wrong settings.xml plugin type')
    return {name:root.findtext('./Settings/'+name) for name in ('ExpMode','ImpMode')}


def structure(node):
    # Ignore indentation only, never whitespace-only leaf field values.
    text=node.text or ''
    if len(node) and not text.strip():text=''
    return (node.tag,tuple(sorted(node.attrib.items())),text,
            tuple((structure(n),n.tail if (n.tail or '').strip() else '') for n in node))


def validate_result(original,candidate,scope):
    old,new=parse_xml(original),parse_xml(candidate)
    if old.attrib!=new.attrib:raise AdapterError('Source attributes must be preserved')
    if scope=='sheet_settings':
        for root in (old,new):
            sheet=root.find('./Schematic/SheetSettings')
            if sheet is None:raise AdapterError('SheetSettings missing in full exchange')
            root.find('Schematic').remove(sheet)
        if structure(old)!=structure(new):raise AdapterError('Edits outside SheetSettings are not allowed')
    elif scope!='full':raise AdapterError('Invalid write scope')


def invoke_worker(request):
    ctx=Context(request)
    print(f'DipTraceSchPluginAdapter {__version__}; API {API_VERSION}; '
          f'plugin {ctx.plugin_id}; plugin version {ctx.plugin_version or "unspecified"}',flush=True)
    try:
        sys.path.insert(0,str(ctx.plugin_dir))
        spec=importlib.util.spec_from_file_location('_dt_plugin_'+uuid.uuid4().hex,ctx._data['entry'])
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        result=module.main(ctx)
        if result not in (None,0):raise AdapterError('main(context) returned nonzero: '+str(result))
        ctx.read_xml()  # Detect accidental edits to the capture before publication.
        status='cancelled' if ctx._cancelled else 'changed' if ctx._staged else 'ok'
        json_write(ctx.run_dir/'status.json',{'api_version':API_VERSION,'adapter_version':__version__,
                                            'status':status,'result_sha256':ctx._staged})
        return 0
    except BaseException:
        ctx.cancel()
        message=traceback.format_exc()
        ctx.log(message)
        json_write(ctx.run_dir/'status.json',{'api_version':API_VERSION,'adapter_version':__version__,
                                            'status':'error','error':message})
        return 1


def publish_result(run,original):
    run=Path(run);original=Path(original)
    request=json.loads((run/'context.json').read_text(encoding='utf-8'))
    status=json.loads((run/'status.json').read_text(encoding='utf-8'))
    if status['status']!='changed':return False
    if request['mode']!='ui':raise AdapterError('Read-only invocation cannot publish')
    before=(run/'exchange.xml').read_bytes()
    digest=hashlib.sha256(before).hexdigest()
    if digest!=request['source_sha256'] or hashlib.sha256(original.read_bytes()).hexdigest()!=digest:
        raise AdapterError('Exchange changed while plugin was open; result was not applied')
    data=(run/'result.xml').read_bytes()
    if hashlib.sha256(data).hexdigest()!=status['result_sha256']:raise AdapterError('Staged result hash mismatch')
    validate_result(before,data,request['write_scope'])
    if data==before:return False
    atomic_write(original,data)
    json_write(run/'applied.json',{'applied':True,'sha256':status['result_sha256']})
    return True


def launch(config,exchange):
    config=Path(config).resolve();exchange=Path(exchange).resolve()
    c,request=read_config(config)
    before=exchange.read_bytes();parse_xml(before)
    raw=c.get('adapter','capture_dir',fallback='').strip()
    if raw:
        base=Path(os.path.expandvars(raw));base=base if base.is_absolute() else config.parent/base
    else:base=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'DipTraceSchPluginAdapter'/request['plugin_id']/'captures'
    run=base/(datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex)
    run.mkdir(parents=True,exist_ok=False)
    request['source_sha256']=hashlib.sha256(before).hexdigest()
    atomic_write(run/'exchange.xml',before)
    json_write(run/'context.json',request)
    json_write(base/'latest.json',{'run_dir':str(run),'api_version':1})
    # BOMJob compatibility: only a copied capture, never the DipTrace temp file.
    json_write(run/'capture.json',{'mode':'run','captured_xml':str(run/'exchange.xml')})
    json_write(run/'status.json',{'api_version':API_VERSION,'adapter_version':__version__,'status':'starting'})
    with (run/'worker.log').open('wb') as stream:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'host.py'),
                                  '--worker',str(run/'context.json')],cwd=request['plugin_dir'],
                                 stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,close_fds=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if request['mode']=='job':
        # Reap children when embedded in a long-lived test/dev process. The
        # daemon waiter never delays the short-lived native host's exit.
        threading.Thread(target=process.wait,daemon=True).start()
        return 0  # XML is safely captured before CAD resumes.
    code=process.wait()
    if code:raise AdapterError('Plugin failed; original exchange unchanged. See '+str(run/'plugin.log'))
    publish_result(run,exchange)
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',action='version',version=f'DipTraceSchPluginAdapter {__version__}, API {API_VERSION}')
    parser.add_argument('--config',type=Path);parser.add_argument('--exchange',type=Path)
    parser.add_argument('--worker',type=Path)
    args=parser.parse_args(argv)
    if args.worker:return invoke_worker(args.worker)
    if args.config is None or args.exchange is None:parser.error('--config and --exchange required')
    try:return launch(args.config,args.exchange)
    except Exception as error:
        detail=traceback.format_exc()
        base=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'DipTraceSchPluginAdapter'
        try:atomic_write(base/'last_error.log',detail.encode('utf-8'))
        except OSError:pass
        if sys.stderr is not None:print(detail,file=sys.stderr)
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(error),f'DipTraceSchPluginAdapter {__version__}',0x10)
        return 1
