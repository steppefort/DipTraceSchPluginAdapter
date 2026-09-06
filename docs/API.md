# API 1 and lifecycle

## Bootstrap

DipTrace starts the renamed EXE with one positional path to its temporary XML.
EXE resolves adapter.ini and .adapter/host.py beside itself, never against CAD's
working directory. It launches Python without a console, inherits the process
environment, and waits for the short host process. The host copies the exchange
before launching the worker. In job mode it returns immediately after successful
process creation. In ui mode it waits for the worker and conditionally publishes.

The mode is a lifecycle policy, independent of the GUI toolkit. A worker callback
can use Tkinter, Qt or another UI, but the window's event loop must finish before
main returns. Background threads must not outlive a staged UI result.

## Request

context.json is UTF-8 JSON. API-v1 keys:

| Key | Meaning |
| --- | --- |
| api_version | Integer 1; incompatible versions rejected |
| mode | job or ui |
| plugin_id | ASCII identifier used for diagnostics |
| plugin_dir | Absolute plugin directory |
| entry | Absolute business Python entry |
| config_path | Absolute adapter.ini |
| source_sha256 | Hash of exchange.xml in this run directory |
| write_scope | sheet_settings or full |
| settings | ExpMode and ImpMode validated at startup |

The context is per invocation, not a persistent project connection. Do not cache
it for subsequent opens of another project. Worker input is always exchange.xml
beside context.json. Original temporary CAD paths are not needed by callbacks.

## Result

status.json contains api_version and status:

| Status | Meaning |
| --- | --- |
| starting | Worker has not completed |
| ok | Successful callback, no XML staged |
| changed | Successful callback with result.xml and result_sha256 |
| cancelled | Explicit cancellation |
| error | Callback failed; error traceback and no publishable result |

The host accepts changed only in ui mode, verifies the candidate hash, validates
XML type and write scope, rechecks the original exchange hash, then atomically
replaces the original temporary file. applied.json records the completed write.
A successful native exit in job mode means launch succeeded, not worker completion.
There is no update download or package installation in the launch path.

## XML scope

The default sheet_settings policy permits edits only within
/Source/Schematic/SheetSettings. Everything else is structurally compared,
including unknown nodes/attributes. Inter-element whitespace is ignored; leaf
text is not. Root attributes cannot change even with full scope. DTD/entities
are rejected. Validation is structural, not a complete DipTrace schema validator.

Full scope is an explicit author choice: it allows a complete XML round trip,
including modifications/removals. There are no per-object partial patch semantics
in v1. Keep settings.xml export/import settings aligned with the callback.

## Environment

ctx.environment([names]) normalizes case and optional <...>/%...% wrappers. It
selects inherited process values, not the machine's persistent settings. Only
requested variables are saved in selected_environment.json. A snapshot is for
inspection; the generic API does not silently substitute it during manual replay.
BOMJob's existing worker retains its own replay logic through its bridge.

## Compatibility

API_VERSION is independent from release version. Consumers pin the complete
adapter commit, including its EXE and Python runtime. Future incompatible request
or callback contracts increment API_VERSION. Never mix an EXE with an unrelated
runtime manually; use vendor_adapter.py and retain adapter.lock.json.
