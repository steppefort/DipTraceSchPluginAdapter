from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'tools')]
from diptrace_adapter.host import launch,invoke_worker,publish_result,read_config,validate_result
from diptrace_adapter.api import AdapterError,Context,parse_xml
from new_plugin import create
from vendor_adapter import fetch, install
from diptrace_adapter import __version__, API_VERSION
from versioning import sync

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.original=self.root/'original.xml'
        self.before=(ROOT/'tests/schematic.xml').read_bytes();self.original.write_bytes(self.before)
        self.plugin=self.root/'Plugin'

    def setup_plugin(self,mode,code):
        create(self.plugin,'TestPlugin',mode)
        (self.plugin/'plugin.py').write_text(code,encoding='utf-8')
        ini=self.plugin/'adapter.ini'
        text=ini.read_text().replace('capture_dir =','capture_dir = '+str(self.root/'captures'))
        text=text.replace('executable = pyw.exe','executable = '+sys.executable)
        ini.write_text(text,encoding='utf-8')
        return ini

    def run_dir(self):return Path(json.loads((self.root/'captures/latest.json').read_text())['run_dir'])
    def wait_status(self):
        end=time.monotonic()+10
        while time.monotonic()<end:
            status=json.loads((self.run_dir()/'status.json').read_text())
            if status['status']!='starting':return status
            time.sleep(.02)
        self.fail('Worker did not finish')

    def test_ui_commits_after_successful_return(self):
        ini=self.setup_plugin('ui', '''def main(ctx):
    root=ctx.document()
    root.find('.//TextLine').text='Changed heading'
    ctx.commit_xml(root)
''')
        self.assertEqual(launch(ini,self.original),0)
        result=parse_xml(self.original.read_bytes())
        self.assertEqual(result.find('.//TextLine').text,'Changed heading')
        self.assertEqual(result.findtext('./Schematic/Nets/Net/Name'),'KEEP')
        self.assertEqual((self.run_dir()/'exchange.xml').read_bytes(),self.before)
        self.assertTrue((self.run_dir()/'applied.json').exists())

    def test_ui_close_without_commit_does_not_touch_original(self):
        ini=self.setup_plugin('ui','def main(ctx):\n    ctx.document().find(".//TextLine").text="Unsaved"\n')
        launch(ini,self.original)
        self.assertEqual(self.original.read_bytes(),self.before)
        self.assertFalse((self.run_dir()/'applied.json').exists())

    def test_cancel_discards_staged_result(self):
        ini=self.setup_plugin('ui','def main(ctx):\n    ctx.commit_xml(ctx.document())\n    ctx.cancel()\n')
        launch(ini,self.original)
        self.assertEqual(self.original.read_bytes(),self.before)
        self.assertEqual(self.wait_status()['status'],'cancelled')
        self.assertFalse((self.run_dir()/'result.xml').exists())

    def test_exception_after_commit_never_publishes(self):
        ini=self.setup_plugin('ui','def main(ctx):\n    ctx.commit_xml(ctx.document())\n    raise RuntimeError("test failure")\n')
        with self.assertRaises(AdapterError):launch(ini,self.original)
        self.assertEqual(self.original.read_bytes(),self.before)
        self.assertEqual(self.wait_status()['status'],'error')

    def test_job_captures_before_return_and_worker_continues(self):
        ini=self.setup_plugin('job','''import time
from pathlib import Path
def main(ctx):
    gate=ctx.plugin_dir/'gate'
    end=time.monotonic()+10
    while not gate.exists():
        if time.monotonic()>end:raise RuntimeError('No release')
        time.sleep(.02)
    ctx.log('completed')
''')
        self.assertEqual(launch(ini,self.original),0)
        self.assertEqual((self.run_dir()/'exchange.xml').read_bytes(),self.before)
        self.assertEqual(json.loads((self.run_dir()/'status.json').read_text())['status'],'starting')
        self.original.unlink()  # DipTrace may discard its temp file after adapter exit.
        (self.plugin/'gate').touch()
        self.assertEqual(self.wait_status()['status'],'ok')

    def test_job_writeback_is_rejected(self):
        ini=self.setup_plugin('job','def main(ctx):\n    ctx.commit_xml(ctx.document())\n')
        launch(ini,self.original)
        self.assertEqual(self.wait_status()['status'],'error')
        self.assertEqual(self.original.read_bytes(),self.before)

    def test_job_requires_import_none(self):
        ini=self.setup_plugin('job','def main(ctx):pass\n')
        p=self.plugin/'settings.xml';p.write_text(p.read_text().replace('<ImpMode>None','<ImpMode>All'))
        with self.assertRaisesRegex(AdapterError,'ImpMode=None'):read_config(ini)

    def test_ui_requires_full_exchange(self):
        ini=self.setup_plugin('ui','def main(ctx):pass\n')
        p=self.plugin/'settings.xml';p.write_text(p.read_text().replace('<ExpMode>All','<ExpMode>Partial'))
        with self.assertRaisesRegex(AdapterError,'ExpMode=All'):read_config(ini)

    def test_sheet_scope_prevents_other_edits(self):
        root=parse_xml(self.before);root.find('./Schematic/Nets/Net/Name').text='UNWANTED'
        candidate=ET.tostring(root)
        with self.assertRaisesRegex(AdapterError,'outside SheetSettings'):validate_result(self.before,candidate,'sheet_settings')
        validate_result(self.before,candidate,'full')

    def test_invalid_xml_and_entities_rejected(self):
        for data in [b'<Source/>',b'<!DOCTYPE Source><Source/>',b'<Source Type="DipTrace-PCB"><Schematic/></Source>']:
            with self.subTest(data=data),self.assertRaises(AdapterError):parse_xml(data)

    def test_source_changed_during_ui_prevents_commit(self):
        ini=self.setup_plugin('ui','def main(ctx):pass\n')
        launch(ini,self.original)
        ctx=Context(self.run_dir()/'context.json')
        ctx.commit_xml(ctx.document())
        (ctx.run_dir/'status.json').write_text(json.dumps({'status':'changed','result_sha256':ctx._staged}))
        self.original.write_bytes(self.before+b'\n')
        with self.assertRaisesRegex(AdapterError,'changed while'):publish_result(self.run_dir(),self.original)
        self.assertEqual(self.original.read_bytes(),self.before+b'\n')

    def test_environment_selection_case_insensitive_no_unrelated_dump(self):
        ini=self.setup_plugin('ui','def main(ctx):pass\n');launch(ini,self.original)
        ctx=Context(self.run_dir()/'context.json')
        with patch.dict(os.environ,{'<Company>':'Example','AUTHOR':'Engineer','SECRET':'do-not-export'},clear=True):
            self.assertEqual(ctx.environment(['company','author']),{'company':'Example','author':'Engineer'})
        data=(ctx.run_dir/'selected_environment.json').read_text()
        self.assertNotIn('SECRET',data);self.assertNotIn('do-not-export',data)

    def test_release_metadata_and_python_cli_agree(self):
        info=sync(check=True)
        self.assertEqual(__version__,info['version'])
        self.assertEqual(API_VERSION,info['api_version'])
        text=subprocess.check_output([sys.executable,str(ROOT/'python/host.py'),'--version'],text=True)
        self.assertEqual(text.strip(),f'DipTraceSchPluginAdapter {__version__}, API {API_VERSION}')

    def test_plugin_version_is_independent_and_survives_adapter_update(self):
        create(self.plugin,'TestPlugin','ui',plugin_version='2.3.4')
        manifest=ET.parse(self.plugin/'settings.xml').getroot()
        self.assertEqual(manifest.get('Name'),'TestPlugin 2.3.4')
        self.assertEqual(manifest.get('ExeFile'),'TestPlugin.exe')
        ini=self.plugin/'adapter.ini'
        text=ini.read_text().replace('capture_dir =','capture_dir = '+str(self.root/'captures'))
        ini.write_text(text)
        (self.plugin/'plugin.py').write_text('def main(ctx):\n    ctx.log(ctx.adapter_version + " / " + ctx.plugin_version)\n')
        self.assertEqual(launch(ini,self.original),0)
        ctx=Context(self.run_dir()/'context.json')
        self.assertEqual(ctx.adapter_version,__version__)
        self.assertEqual(ctx.plugin_version,'2.3.4')
        self.assertEqual(ctx.plugin_id,'TestPlugin')
        self.assertIn(__version__+' / 2.3.4',(ctx.run_dir/'plugin.log').read_text())
        self.assertIn('plugin version 2.3.4',(ctx.run_dir/'worker.log').read_text())
        self.assertEqual(self.wait_status()['adapter_version'],__version__)
        before=(self.plugin/'settings.xml').read_bytes()
        lock=install(ROOT,self.plugin,'TestPlugin.exe','local-checkout','test')
        self.assertEqual(lock['adapter_version'],__version__)
        self.assertEqual((self.plugin/'settings.xml').read_bytes(),before)
        self.assertEqual(ini.read_text(),text)

    def test_vendoring_rejects_a_stale_binary_version(self):
        repo=self.root/'stale';repo.mkdir()
        (repo/'dist').mkdir()
        shutil.copy2(ROOT/'dist/DipTraceSchPluginAdapter.exe',repo/'dist')
        shutil.copytree(ROOT/'python',repo/'python')
        info=json.loads((ROOT/'build_info.json').read_text());info['version']='9.9.9'
        (repo/'build_info.json').write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError,'stale'):
            install(repo,self.plugin,'TestPlugin.exe','local-checkout','test')
        self.assertFalse(self.plugin.exists())

    def test_native_binary_is_x64_gui(self):
        b=(ROOT/'dist/DipTraceSchPluginAdapter.exe').read_bytes();off=struct.unpack_from('<I',b,0x3c)[0]
        self.assertEqual(b[:2],b'MZ');self.assertEqual(b[off:off+4],b'PE\0\0')
        self.assertEqual(struct.unpack_from('<H',b,off+4)[0],0x8664)
        self.assertEqual(struct.unpack_from('<H',b,off+24+68)[0],2)

    def test_pinned_dependency_fetch_and_hashes(self):
        repo=self.root/'repo';repo.mkdir();shutil.copytree(ROOT/'python',repo/'python')
        shutil.copy2(ROOT/'build_info.json',repo/'build_info.json')
        (repo/'dist').mkdir();shutil.copy2(ROOT/'dist/DipTraceSchPluginAdapter.exe',repo/'dist')
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
        revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        dest=self.root/'consumer'
        lock=fetch(str(repo),revision,dest,'Renamed.exe')
        self.assertEqual(lock['commit'],revision)
        for file,digest in lock['files'].items():self.assertEqual(hashlib.sha256((dest/file).read_bytes()).hexdigest(),digest)
        with self.assertRaises(ValueError):fetch(str(repo),'main',dest,'Renamed.exe')

    @unittest.skipUnless(os.name=='nt','Requires Windows native process execution')
    def test_native_windows_launch_renamed_exe(self):
        self.setup_plugin('ui','def main(ctx):\n    root=ctx.document()\n    root.find(".//TextLine").text="Native tested"\n    ctx.commit_xml(root)\n')
        host=self.plugin/'.adapter/host.py'
        host.write_text('import sys\nprint("host stdout marker",flush=True)\n'
                        'print("host stderr marker",file=sys.stderr,flush=True)\n'+
                        host.read_text(encoding='utf-8'),encoding='utf-8')
        temp=self.root/'native logs';temp.mkdir()
        env=dict(os.environ,TEMP=str(temp),TMP=str(temp))
        p=subprocess.run([str(self.plugin/'TestPlugin.exe'),str(self.original)],env=env,timeout=30)
        self.assertEqual(p.returncode,0)
        self.assertEqual(parse_xml(self.original.read_bytes()).find('.//TextLine').text,'Native tested')
        logs=list((temp/'DipTraceSchPluginAdapter').glob('launch-*.log'))
        self.assertEqual(len(logs),1)
        text=logs[0].read_text(encoding='utf-8')
        for marker in ('host stdout marker','host stderr marker','Python exit code: 0',
                       'Resolved interpreter: '+sys.executable,'Python command: '):
            self.assertIn(marker,text)

    @unittest.skipUnless(os.name=='nt','Requires the Windows Python launcher')
    def test_native_windows_py_version_selector(self):
        launcher=shutil.which('py.exe')
        if not launcher:self.skipTest('py.exe is not installed')
        self.plugin=self.root/'Plugin with spaces'
        ini=self.setup_plugin('ui','def main(ctx):\n    root=ctx.document()\n    root.find(".//TextLine").text="Python launcher tested"\n    ctx.commit_xml(root)\n')
        ini.write_text(ini.read_text().replace('executable = '+sys.executable,
                                             'executable = '+launcher),encoding='utf-8')
        temp=self.root/'py logs';temp.mkdir()
        env=dict(os.environ,TEMP=str(temp),TMP=str(temp))
        process=subprocess.run([str(self.plugin/'TestPlugin.exe'),str(self.original)],
                               cwd=self.root,env=env,timeout=30)
        self.assertEqual(process.returncode,0)
        self.assertEqual(parse_xml(self.original.read_bytes()).find('.//TextLine').text,
                         'Python launcher tested')
        logs=list((temp/'DipTraceSchPluginAdapter').glob('launch-*.log'))
        self.assertEqual(len(logs),1)
        log=logs[0].read_text(encoding='utf-8')
        command=next(line for line in log.splitlines() if line.startswith('Python command:'))
        self.assertIn(' -3 "',command)
        self.assertNotIn(' "-3" ',command)
        self.assertIn('Python exit code: 0',log)

    @unittest.skipUnless(os.name=='nt','Requires Windows PATH lookup and native process execution')
    def test_native_windows_interpreter_found_only_through_path(self):
        ini=self.setup_plugin('ui', 'def main(ctx):\n    root=ctx.document()\n    root.find(".//TextLine").text="PATH lookup tested"\n    ctx.commit_xml(root)\n')
        interpreter=Path(sys.executable)
        self.assertNotEqual(interpreter.parent, self.plugin)
        self.assertNotEqual(interpreter.parent, self.root)
        text=ini.read_text().replace('executable = '+sys.executable,
                                     'executable = '+interpreter.name)
        ini.write_text(text,encoding='utf-8')
        environment=dict(os.environ)
        environment['PATH']=str(interpreter.parent)+os.pathsep+environment.get('PATH','')
        process=subprocess.run([str(self.plugin/'TestPlugin.exe'),str(self.original)],
                               cwd=self.root,env=environment,timeout=30)
        self.assertEqual(process.returncode,0)
        self.assertEqual(parse_xml(self.original.read_bytes()).find('.//TextLine').text,
                         'PATH lookup tested')

if __name__=='__main__':unittest.main()
