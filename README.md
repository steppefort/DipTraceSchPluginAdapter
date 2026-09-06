# DipTraceSchPluginAdapter

Reusable Windows x64 EXE + Python runtime for DipTrace Schematic plugins.
Version **0.1.0**, API **1**, MIT license. Independent community project.

The EXE can be renamed for each plugin without recompilation. A plugin supplies
`adapter.ini`, DipTrace's `settings.xml`, and `plugin.py` with `main(context)`.
No BOM grouping, OTS formatting, VPT editing or title replacement rules live in
this adapter. Python 3.11+ must be installed; Python is not embedded in the EXE.

| Mode  | Lifecycle                                                        | Project writeback                 |
| ----- | ---------------------------------------------------------------- | --------------------------------- |
| `job` | Capture XML, start worker, release DipTrace; worker exits itself | Disabled; `ImpMode=None` required |
| `ui`  | Keep adapter alive until UI closes; publish on successful return | Explicit `ctx.commit_xml()` only  |

UI mode is synchronous from DipTrace's perspective: changes are imported after
its launched EXE exits. This is a file exchange API, not a live RPC connection.

## Try the examples

From the repository root:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\DemoJob --name DemoJob --mode job
py -3 tools/new_plugin.py D:\PluginBuild\DemoUI --name DemoUI --mode ui
```

Copy either generated directory to `DipTrace\Plugins\Schematic\`, restart
Schematic Capture, then choose it in Tools > Plugins. Keep only one EXE in each
plugin root. The UI example edits the text below `Designed by` after Apply; it
is not the existing TitleJob UI/VPT editor.

The scaffold bundles the checked-out adapter, ready for offline installation:

```text
DemoUI/
  DemoUI.exe
  settings.xml
  adapter.ini
  adapter.lock.json
  plugin.py
  .adapter/
    host.py
    diptrace_adapter/
```

`adapter.ini` is UTF-8 (optional BOM) or UTF-16LE with BOM:

```ini
[adapter]
api_version = 1
plugin_id = DemoUI
mode = ui
write_scope = sheet_settings
capture_dir =

[python]
executable = pyw.exe

[plugin]
entry = plugin.py
```

If `pyw.exe` is unavailable, set `executable` to the full path to `pythonw.exe`
without quotes. The bootstrap interpreter does not expand `%VAR%` expressions.
The launcher passes `-3` only for `py.exe`/`pyw.exe`. Other Python flags are not
part of bootstrap API v1. No terminal window is created.

## Plugin API

```python
def main(ctx):
    document = ctx.document()
    variables = ctx.environment(["author", "Company"])
    # Business logic and GUI live here.
    ctx.log("Started")
    # UI only, after the user's Apply action:
    # ctx.commit_xml(document)
```

- `ctx.exchange_path`: captured XML; must not be modified.
- `ctx.read_xml()`: original bytes, checked against the capture hash.
- `ctx.document()`: fresh ElementTree root; preserves comments and unknown nodes.
- `ctx.project_dir`: project path from XML, or `None`.
- `ctx.plugin_dir`, `ctx.run_dir`, `ctx.plugin_id`, `ctx.mode`.
- `ctx.environment(names)`: selected inherited values, with case-insensitive keys.
- `ctx.commit_xml(bytes_or_root)`: stage a full exchange; UI only.
- `ctx.cancel()`: discard pending changes.
- `ctx.log(message)`: append to the run log.

`main` returns `None` or `0`. An exception/nonzero result discards staged XML.
Returning without commit also leaves the original file unchanged. Commit stages
an edit; publication occurs only after `main` successfully returns. See
[API and lifecycle](docs/API.md).

`write_scope=sheet_settings` is the default and compares the rest of the XML
before publication. `write_scope=full` explicitly permits other schematic edits.
API v1 UI requires `ExpMode=All` + `ImpMode=All` and a complete returned XML.
Per-object partial Edit APIs are outside this first release.

## Depend on the root repository

After publishing this repository, each consumer pins an actual commit SHA:

```powershell
py -3 tools/vendor_adapter.py --repo https://github.com/OWNER/DipTraceSchPluginAdapter.git --commit FULL_40_CHARACTER_COMMIT_SHA --dest D:\PluginBuild\MyPlugin --exe MyPlugin.exe
```

`OWNER` and the SHA are placeholders, not a pre-existing published repository.
The tool fetches exactly that commit and copies only the EXE and Python runtime.
It writes `adapter.lock.json` with the repository, commit and file hashes. It
preserves plugin.py, INI and settings.xml. Stop running plugin processes before
updating an installed runtime; `.adapter.previous` retains the previous runtime.

An alternative for development is a pinned Git submodule under
`vendor/DipTraceSchPluginAdapter`; run its vendoring/scaffolding tools when
assembling a plugin release. Do not run `git pull` from the user's CAD plugin:
updates happen at build/install time and installations work offline.

Keep `dist/DipTraceSchPluginAdapter.exe` in the root repository alongside source,
so a consumer does not need a C compiler. Tests and documentation stay in the
root repository, not in the installed plugin runtime.

## Build and test

The included EXE was cross-compiled with Zig 0.14.1:

```powershell
py -3 -m pip install ziglang==0.14.1
# Locate zig.exe in the installed ziglang package and pass its absolute path:
py -3 tools/build.py --zig C:\path\to\zig.exe
py -3 -m unittest discover -s tests -v
```

The build tool checks PE x64 and Windows GUI subsystem. CI builds the executable
and runs tests on Linux and Windows. The native launch test runs only on Windows.

Current local verification: 14 tests passed on Linux; 1 native Windows test
skipped. BOMJob 0.2.7 ran through the bridge, created one ODS in Docs, and left
its original XML unchanged. The new EXE/UI chain has not yet been tested in
DipTrace on Windows. The original TitleJob archive was unavailable during this
extraction; migrating that exact application remains separate from the UI demo.

## Existing plugins

- [BOMJob bridge](examples/bomjob_bridge/plugin.py): place it as plugin.py beside
  the existing BOMJob 0.2.7 business files; use mode=job and ImpMode=None. Keep
  bomjob.ini and templates. Its existing environment/ODS logic is reused.
- TitleJob: preserve its business UI and VPT rules, change the entry to main(ctx),
  read the capture via ctx, and stage its final complete XML with commit_xml.
  See [migration notes](docs/MIGRATION_RU.md). No drop-in TitleJob release is claimed.

## Diagnostics

Each run has its own directory under
`%LOCALAPPDATA%\DipTraceSchPluginAdapter\<plugin_id>\captures` unless overridden.
It contains context.json, exchange.xml, status.json, worker.log, optional
plugin.log/result.xml/applied.json and explicitly requested environment values.
A job may be still running when the native launcher exits successfully; inspect
status.json for worker success. No automatic capture cleanup is implemented.
Captures remain private local project data; the repository tests use synthetic XML.

This API does not create/edit DipTrace Tools > Environment Variables; it reads
values inherited by the child process. It is not a security sandbox for plugin
code. Export/import policy is validated by the adapter, but arbitrary Python
plugins execute with the user's permissions.

## Reference

The public protocol is documented by Novarm in
[DipTrace plugin architecture and SDK](https://diptrace.com/support/tutorials/)
and the [plugin specification](https://diptrace.com/books/DipTrace_Plugins.pdf).
The official SDK is not redistributed here. DipTrace is a Novarm product;
this adapter is an independent project.
