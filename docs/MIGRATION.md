# Migrate an existing plugin to DipTraceSchPluginAdapter

English · [Українська](MIGRATION_UA.md) · [README](../README.md) · [API](API.md)

This guide describes how to replace an existing plugin's launcher and XML exchange code with DipTraceSchPluginAdapter. The plugin keeps its application code, interface, settings, and templates. BOMJob and TitleJob illustrate the two supported modes.

## What belongs where

| Adapter repository | Individual plugin package |
| --- | --- |
| Native launcher source and prebuilt EXE | A copy of the EXE renamed for the plugin |
| Python API and runtime source | Runtime modules in `.adapter` |
| Scaffolding and dependency tools, tests, CI, and documentation | `plugin.py`, application modules, configuration, templates, and other resources |

Pin the adapter to a specific repository commit. Use `tools/vendor_adapter.py` when preparing a plugin release to obtain the matching EXE and runtime modules. Users of a packaged plugin do not need Git or a compiler, but do need Python and any packages required by the plugin.

To adopt a newer adapter version, update the pinned commit and rebuild the plugin package. The plugin does not run `git pull` or download updates when launched from DipTrace. See [dependency setup](../README.md#use-the-adapter-repository-as-a-dependency).

## General migration procedure

1. Create a new plugin folder with `tools/new_plugin.py`. Choose `job` for background tasks that produce files, or `ui` for an editor that returns schematic changes.
2. Copy the existing plugin's application modules, configuration files, and resources into the new folder. Keep the generated EXE, `.adapter`, `adapter.ini`, and `settings.xml`.
3. Implement `main(ctx)` in `plugin.py`. Read the captured input through `ctx.read_xml()` or `ctx.document()` and use context paths for resources and output.
4. For an editor, stage the complete modified document with `ctx.commit_xml()` after user confirmation. Finish the event loop and return from `main()` so that the adapter can return the result to DipTrace.
5. Check the new plugin in DipTrace before replacing the existing installation. Verify both successful execution and cancellation or failure behavior.

Do not copy the old launcher EXE or startup scripts into the new package. Keep one EXE in the plugin folder, with a matching `ExeFile` value in `settings.xml`.

## BOMJob 0.2.7: background task

BOMJob generates an ODS file without returning edits to the schematic, so it uses `job` mode.

### 1. Create a separate plugin folder

From the adapter repository root, in PowerShell:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\BOMJobNext --name BOMJobNext --mode job
```

The destination must not already exist. This creates a complete scaffold containing the renamed adapter and a demonstration `plugin.py`.

### 2. Copy the BOMJob application files

Copy the following from the working BOMJob 0.2.7 installation into `D:\PluginBuild\BOMJobNext`:

- `bomjob.py`, `bom_core.py`, `bom_output.py`, and `bom_page_labels.py`.
- `diptrace_environment.py` and `inspect_xml.py`.
- `bomjob.ini` and the `templates` directory, including the templates referenced by the configuration.

Retain any additional resources referenced by your configuration. Check paths that refer to the previous installation directory.

### 3. Replace the demonstration entry point

Copy [`examples/bomjob_bridge/plugin.py`](../examples/bomjob_bridge/plugin.py) to `D:\PluginBuild\BOMJobNext\plugin.py`, replacing the generated example. The bridge calls the existing BOMJob worker with the captured XML, the plugin's `bomjob.ini`, and `--pause never`.

`adapter.ini` configures the shared launcher and runtime. `bomjob.ini` continues to configure BOM generation. The old launcher and its startup configuration are not used by the adapter.

### 4. Check the settings and output

Keep `mode=job` in `adapter.ini` and `ExpMode=All`, `ImpMode=None` in `settings.xml`. Configure the Python executable as described in the [README](../README.md).

Install the complete new folder in DipTrace and run it on a test project. Check the generated ODS, the output path specified by the BOM configuration, and the worker's final `status.json`. Confirm that the schematic is unchanged. A successful EXE exit in `job` mode confirms worker startup, not completion of BOM generation.

## TitleJob: editor with Apply and Cancel

TitleJob uses `ui` mode because it returns changes to title-block fields. Its interface, VPT handling, and replacement rules remain part of TitleJob; the shared adapter handles startup and XML exchange.

Create a separate scaffold from the adapter repository root:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\TitleJobNext --name TitleJobNext --mode ui
```

Copy the existing TitleJob application modules and resources, then adapt the integration points below.

| Integration point | Adapter API or setting |
| --- | --- |
| Entry point | `main(ctx)` |
| Input XML | `ctx.read_xml()` or `ctx.document()` |
| Requested environment variables | `ctx.environment(["author", "Company"])` |
| Apply handler | Modify the complete document and call `ctx.commit_xml(document)` |
| Cancel or window close without applying | Call `ctx.cancel()` and close the window |
| Execution mode | `mode=ui` in `adapter.ini` |
| Title-block write scope | `write_scope=sheet_settings` in `adapter.ini` |
| XML exchange | `ExpMode=All` and `ImpMode=All` in `settings.xml` |

Keep the GUI event loop inside `main()`. After a successful Apply, close the window and let `main()` return. The adapter validates the staged XML and writes it back to the exchange file; DipTrace imports it after the EXE exits. An exception after `commit_xml()` discards the staged result. Files saved directly by TitleJob, such as VPT templates, are not automatically rolled back.

The [UI example](../examples/ui/plugin.py) demonstrates matching `Designed by` by its first line and replacing the lines below it. It is not a complete TitleJob implementation. Preserve the editor's tabs, rule table, template operations, and validation in the application code.

`ctx.environment()` reads inherited process values and returns normalized keys; for example, `Company` is returned as `company`. It does not create or edit project variables in DipTrace. Changing `os.environ` inside the plugin does not save those changes to the project.

Test Apply, Cancel, missing variables, and fields with existing multiline text. Confirm that the first line of each matched title-block field is preserved and that unrelated schematic data remains unchanged.
