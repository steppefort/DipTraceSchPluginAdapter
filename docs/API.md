# API 1: plugin interface and lifecycle

English · [Українська](API_UA.md) · [README](../README.md)

This document describes how DipTraceSchPluginAdapter starts a plugin, provides its input, and returns changes to DipTrace. For installation and a step-by-step plugin example, see the [README](../README.md).

## Startup and execution

DipTrace starts the plugin EXE with one positional argument: the path to a temporary XML exchange file. The EXE locates `adapter.ini` and `.adapter/host.py` beside itself, independently of DipTrace's working directory.

The startup sequence is:

1. The EXE starts the Python host without a console window. Python inherits the launcher's process environment.
2. The host validates the configuration and input XML, creates a run directory, and saves a copy of the XML as `exchange.xml`.
3. The host writes `context.json` and starts a separate Python worker process that calls `main(ctx)` from the plugin's entry file.
4. In `job` mode, the host returns once the worker has started, allowing the EXE to exit and DipTrace to resume. The worker continues independently.
5. In `ui` mode, the host waits for the worker to finish. If the worker succeeds and has staged a result, the host validates it and writes it to the original exchange file before the EXE exits.

| Mode | Required exchange settings in `settings.xml` | Returning schematic changes |
| --- | --- | --- |
| `job` | `ImpMode=None` | Not allowed. |
| `ui` | `ExpMode=All` and `ImpMode=All` | Allowed through `ctx.commit_xml()`. |

The mode controls execution and import behavior, not the GUI toolkit. Plugins may use Tkinter, Qt, or another toolkit. Keep the window's event loop inside `main()` and finish any work that affects the returned XML before `main()` returns.

DipTrace imports changes after the plugin EXE exits. The context represents one invocation; it does not provide a persistent connection to the active project.

## Plugin entry point

The entry file specified by `[plugin] entry` in `adapter.ini` must define:

```python
def main(ctx):
    document = ctx.document()
    variables = ctx.environment(["author", "Company"])
    ctx.log("Plugin started")
    # Implement the plugin here.
```

The adapter supplies `ctx`. Return `None` or `0` on success. An exception or a nonzero return value marks the run as failed and discards any staged XML.

For an editor, call `ctx.commit_xml(document)` after the user confirms the changes, then let `main()` finish. The call stages the result; it does not immediately update the schematic. Calling `ctx.cancel()` discards a staged result. Returning without staging a result also leaves the schematic unchanged.

These rules apply to the XML returned to DipTrace. Files created or changed directly by plugin code are not automatically rolled back.

## Context API

| Method or property | Description |
| --- | --- |
| `ctx.exchange_path` | Path to the captured `exchange.xml`. Do not modify this file. |
| `ctx.read_xml()` | Returns the original XML bytes after verifying their SHA-256 hash. |
| `ctx.document()` | Returns a fresh `xml.etree.ElementTree.Element` root parsed from the capture, preserving comments, processing instructions, and unknown nodes. |
| `ctx.project_dir` | A `pathlib.Path` from `/Source/Schematic/Settings/ProjectDir`, or `None` if it is absent or empty. A relative value is resolved against the plugin directory. |
| `ctx.plugin_dir` | The plugin directory as a `pathlib.Path`. |
| `ctx.run_dir` | The current run directory as a `pathlib.Path`. |
| `ctx.plugin_id`, `ctx.mode` | The identifier and mode for this invocation. |
| `ctx.environment(names)` | Returns the requested inherited environment variables with normalized keys. See [Environment variables](#environment-variables). |
| `ctx.commit_xml(bytes_or_root)` | Stages a complete XML document supplied as `bytes` or an `Element` root. Available only in `ui` mode. |
| `ctx.cancel()` | Discards the staged result and marks the invocation as cancelled. Further commits are rejected. |
| `ctx.log(message)` | Appends a message to `plugin.log`. |

Use the context only for its current invocation. Do not reuse it after opening another project. Plugin code reads the capture and does not need the path to DipTrace's original temporary file.

## Request file

`context.json` is a UTF-8 JSON file in the run directory. Its API 1 fields are:

| Key | Description |
| --- | --- |
| `api_version` | Integer `1`. Incompatible versions are rejected. |
| `mode` | `job` or `ui`. |
| `plugin_id` | ASCII plugin identifier used for diagnostics. |
| `plugin_dir` | Absolute path to the plugin directory. |
| `entry` | Absolute path to the plugin's Python entry file. |
| `config_path` | Absolute path to `adapter.ini`. |
| `source_sha256` | SHA-256 hash of this run's `exchange.xml`. |
| `write_scope` | `sheet_settings` or `full`. |
| `settings` | An object containing `ExpMode` and `ImpMode`, validated at startup. |

The worker always reads `exchange.xml` beside `context.json`. The capture must remain unchanged throughout the invocation.

## Result and import

`status.json` contains `api_version` and `status`. Successful and cancelled worker runs also include `result_sha256`, set to the staged result's hash or `null`. Failed runs include an `error` field containing the traceback.

| Status | Meaning |
| --- | --- |
| `starting` | The run has been initialized; the worker has not yet recorded a final status. |
| `ok` | `main()` completed successfully without staging XML. |
| `changed` | `main()` completed successfully with a staged `result.xml` and its `result_sha256`. |
| `cancelled` | The plugin explicitly cancelled the invocation. |
| `error` | Execution failed; no result is available for import. |

The host accepts `changed` only in `ui` mode. Before returning the result, it:

1. Verifies that the captured XML and the original exchange file still match `source_sha256`.
2. Checks `result.xml` against `result_sha256`.
3. Validates the XML document type and configured scope of changes.
4. Atomically replaces the original exchange file if the result differs from the input, then records the write in `applied.json`.

`changed` means a result was staged, not that DipTrace has already imported it. `applied.json` confirms a write to the exchange file; DipTrace performs the import after the EXE exits. If the result is byte-for-byte identical to the input, the host does not rewrite the file or create `applied.json`.

In `job` mode, a successful EXE exit confirms that the worker was started. Check `status.json` for completion of the task itself. No dependency downloads or package installations occur during startup.

## Scope of XML changes

The `[adapter] write_scope` setting controls which parts of the XML may change:

| Value | Permitted changes |
| --- | --- |
| `sheet_settings` | Only within `/Source/Schematic/SheetSettings`. This is the default. |
| `full` | Changes throughout the schematic XML, including modifications and removals. Root `Source` attributes must still be preserved. |

With `sheet_settings`, the adapter structurally compares everything outside `SheetSettings`, including unknown nodes and attributes. It ignores whitespace used for indentation between elements, but preserves the significance of leaf text.

Return the complete XML document in either scope. API 1 does not support returning patches for individual objects. Keep the export/import settings in `settings.xml` consistent with the chosen mode and the plugin's behavior.

The adapter rejects DTD and entity declarations. Its checks validate document structure and the permitted scope of changes; they are not a complete validation against the DipTrace XML schema.

## Environment variables

`ctx.environment(["author", "Company"])` reads selected values from the environment inherited by the Python process. It does not read persistent Windows system settings and does not create or edit variables in DipTrace's **Tools > Environment variables**.

Names are stripped of surrounding whitespace, may optionally be wrapped in `<...>` or `%...%`, and are normalized using `str.casefold()`. Returned dictionary keys use the normalized form: request `Company`, then read `values["company"]`.

Missing variables are omitted from the dictionary; present variables with empty values remain present. If multiple inherited names normalize to the same key but contain different values, the method raises an error.

Only requested variables that were found are saved in `selected_environment.json`. Successive calls accumulate these selected values for the current invocation. The snapshot is for inspection; manual replay does not automatically load its values into the process environment.

## Version compatibility

The API version is separate from the adapter release version. Pin the complete adapter to a specific repository commit, including both the EXE and Python runtime modules. Incompatible changes to the request format or plugin entry-point contract require a new API version.

Use [`tools/vendor_adapter.py`](../tools/vendor_adapter.py) to install or update matching files and retain `adapter.lock.json`. Do not combine an EXE from one adapter version with runtime modules from an unrelated version. See [dependency setup in the README](../README.md#use-the-adapter-repository-as-a-dependency).
