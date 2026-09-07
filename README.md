# DipTraceSchPluginAdapter

English · [Українська](README_UA.md)

**An adapter for writing DipTrace Schematic plugins in Python.** It handles plugin startup and XML exchange with DipTrace, so you can focus on the feature you need: generating documentation, checking a schematic, or filling in title blocks.

You do not need to write and compile a separate EXE for each plugin. Rename the prebuilt `DipTraceSchPluginAdapter.exe` and implement your plugin in ordinary Python files. The API provides access to the XML data exported by DipTrace and selected environment variables inherited from the DipTrace process.

Version **0.1.1**, API **1**, **MIT** license. An independent community project.

## Versions and releases

`build_info.json` in the repository root is the source of the adapter version
and API number. This release is **0.1.1**, API **1**. BOMJob **0.2.7** is a
separate plugin version; it is not an earlier adapter release.

The build tool generates the Python metadata snapshot and native header,
updates the version line in both READMEs, embeds Windows `FileVersion` and
`ProductVersion`, and records the EXE hash in `build_info.json`.
Do not edit generated version files or recorded hashes manually.
The installed Python package reads its generated `build_info.json`;
the native EXE embeds that same version at compile time.

You can identify a downloaded or installed adapter through:

- `DipTraceSchPluginAdapter-0.1.1.zip`, the versioned release archive.
- Windows **Properties → Details** on the EXE, even after renaming it.
- `DipTraceSchPluginAdapter.exe --version`, which opens an information dialog.
- `py -3 python/host.py --version` in the repository, or
  `py -3 .adapter/host.py --version` in an installed plugin folder.
- `adapter_version` in `adapter.lock.json`, `context.json`, and `status.json`,
  plus the native launch log and `worker.log`.
- `diptrace_adapter.__version__` and `diptrace_adapter.API_VERSION` in Python.

The adapter version and the plugin version are independent. To show a plugin's
own version in the DipTrace menu, create it with:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\MyPlugin --name MyPlugin --mode job --plugin-version 0.1.1
```

The menu name becomes **MyPlugin 0.1.1**, while the executable stays
`MyPlugin.exe` and `plugin_id` stays `MyPlugin`. The version is also written to
`[plugin] version` in `adapter.ini`. Omitting `--plugin-version` preserves the
unversioned display name. For an existing plugin, update both `[plugin] version`
and the `Name` attribute in `settings.xml` when releasing it. Updating the
adapter alone does not change the plugin's version or menu name.
`ctx.adapter_version` and `ctx.plugin_version` expose these values separately;
`ctx.plugin_version` is `None` when it was not configured.

To publish an adapter release:

1. Set `version` in the root `build_info.json`; update `changes` and
   [CHANGELOG.md](CHANGELOG.md). Change `api_version` only for an intentionally
   incompatible API, together with the corresponding implementation changes.
2. Run the [build and tests](#build-the-adapter-and-run-tests), then:

   ```powershell
   py -3 tools/versioning.py --check
   py -3 tools/release.py
   ```

   The ZIP appears in `build/releases/`. Packaging refreshes both checksum
   manifests and excludes Git history, local build products, and captures.
3. Review the changes and commit the sources, generated metadata, README files,
   checksum manifests, and `dist/DipTraceSchPluginAdapter.exe`. For this release:

   ```powershell
   git status --short
   git add .
   git commit -m "Release DipTraceSchPluginAdapter 0.1.1"
   git tag -a v0.1.1 -m "DipTraceSchPluginAdapter 0.1.1"
   git push origin main
   git push origin v0.1.1
   ```

4. Create a GitHub Release from tag `v0.1.1` and attach
   `build/releases/DipTraceSchPluginAdapter-0.1.1.zip`.
   GitHub's automatic source ZIP does not replace this named release asset.
5. In consuming projects such as FineBOM, pin the full commit SHA resolved by
   `git rev-parse "v0.1.1^{commit}"` and rebuild the plugin.

An existing published tag identifies an immutable release; use a new version
for later changes. Tests and release packaging do not push commits or publish
GitHub Releases automatically.

## What the adapter includes

- **A Windows x64 EXE** that receives the XML file path from DipTrace and starts Python without a console window.
- **Python runtime modules** that capture the XML, run your plugin code, record diagnostics, and return permitted changes.
- **The `main(ctx)` API** as the entry point for your plugin.
- **A plugin scaffolding tool**, examples, tests, and a tool for updating the adapter dependency.

BOM rules, OTS/VPT processing, and other application features belong in individual plugins. API 1 provides a Python entry point; this version does not include a separate API for other languages.

Python is not bundled into the EXE. The user's computer needs **Python 3.11 or later**. The UI example also requires Tkinter. Developers need Git to obtain the repository and use its dependency tools; users of a packaged plugin do not need Git.

The current launcher targets **Windows x64**. Linux can be used to prepare plugin folders, test Python code, and build the Windows EXE. Support for running this adapter on macOS has not been implemented or verified.

## Two operating modes

| Mode | Lifecycle | Returning changes to the schematic |
| --- | --- | --- |
| `job` | The adapter captures the XML, starts a background process, and releases DipTrace. Python exits when the task finishes. | Not permitted; requires `ImpMode=None` in `settings.xml`. |
| `ui` | The adapter waits for the Python code to finish, including closing its window, then returns any staged result. | Only after an explicit `ctx.commit_xml()` call and successful completion of `main()`. |

Choose `job` for report generation and `ui` for an editor with **Apply/Cancel** buttons. The mode controls the lifecycle and whether changes can be imported; it does not prescribe a GUI toolkit.

In `ui` mode, DipTrace waits for the plugin to finish. Each invocation uses a file exchange, not a persistent connection to the active schematic. Closing the window without a staged result leaves the schematic unchanged.

## Quick start: create and run an example

The commands below use **PowerShell on Windows**. Replace `D:\PluginBuild` with your own working directory if needed.

### 1. Get the repository

```powershell
git clone https://github.com/steppefort/DipTraceSchPluginAdapter.git
cd DipTraceSchPluginAdapter
py -3 --version
git --version
```

Make sure Python is version 3.11 or later. For the UI example, check Tkinter:

```powershell
py -3 -m tkinter
```

A Tkinter test window should open. Close it after checking.

### 2. Create a plugin folder

For an automatic task:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\DemoJob --name DemoJob --mode job
```

For an example with a window:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\DemoUI --name DemoUI --mode ui
```

These are independent commands: run the one for the mode you want, or both. The destination directory **must not already exist**. If it does, the script exits with an error to avoid overwriting files.

`tools/new_plugin.py` performs the following steps:

1. Creates the destination directory and copies `examples/job/plugin.py` or `examples/ui/plugin.py` into it.
2. Creates `adapter.ini` with the selected mode and plugin name.
3. Creates `settings.xml` with `ExpMode=All` and either `ImpMode=None` for `job` or `ImpMode=All` for `ui`.
4. Copies the prebuilt `dist/DipTraceSchPluginAdapter.exe`, renaming it according to `--name`.
5. Copies the Python runtime modules and license notices into `.adapter`.
6. Writes `adapter.lock.json` with the API version, commit identifier, and SHA-256 hashes of the copied files.

**The result is an installable plugin folder containing the demonstration code.** The script prints its path. It does not compile your Python code, install Python, or launch DipTrace. You do not need to rebuild the EXE for this step.

For `DemoUI`, the main generated files are:

| Path inside the plugin folder | Purpose |
| --- | --- |
| `DemoUI.exe` | The renamed prebuilt adapter. |
| `plugin.py` | The example code; this is where you start implementing your own plugin. |
| `adapter.ini` | Mode, Python executable, entry point, and permitted scope of changes. |
| `settings.xml` | The plugin's name in DipTrace, its EXE, and export/import settings. |
| `adapter.lock.json` | Installed dependency information and file hashes. |
| `.adapter/host.py` | The Python runtime entry point. |
| `.adapter/diptrace_adapter/` | The API and XML exchange implementation. |

The value of `--name` is used for the EXE, `plugin_id`, and the initial plugin name in the DipTrace menu. It must contain 1–80 characters: ASCII letters, digits, `_`, `-`, or `.`. The first character must be a letter or digit.

### 3. Configure Python

The generated `adapter.ini` contains this default:

```ini
[python]
executable = pyw.exe
```

If this launcher is unavailable, or you want to select a particular interpreter, specify the absolute path to your `pythonw.exe`, for example:

```ini
[python]
executable = C:\Python312\pythonw.exe
```

Replace this example path with the actual location of Python. Write the path **without quotes**, even if it contains spaces. Expressions such as `%LOCALAPPDATA%` are not expanded in this setting. The adapter adds `-3` only for `py.exe` or `pyw.exe`; additional arguments in `executable` are not supported.

### 4. Install the plugin in DipTrace

1. Copy the **entire** `DemoJob` or `DemoUI` folder, including `.adapter`, into `Plugins\Schematic` under your DipTrace installation directory. A typical path is `C:\Program Files\DipTrace\Plugins\Schematic\DemoUI`.
2. Keep one EXE in the root of each plugin folder. Each plugin needs its own folder.
3. Restart **Schematic Capture**, open a schematic, and select the plugin under **Tools > Plugins**.

The scaffolding tool does not install the plugin automatically. Copying files into `Program Files` may require administrator privileges.

### 5. Check the result

- **DemoJob:** no window opens. The example reads the XML and the `projectname` and `revision` variables, then writes `summary.json` into the run's diagnostics directory. It does not change the schematic. Check that `status.json` reports `ok` to confirm completion.
- **DemoUI:** a window opens with an author field, initially populated from the `author` variable if available. **Apply to active project** finds title-block text fields whose first line is `Designed by`, preserves that line, and replaces all subsequent lines with the entered value. Your schematic needs such a field to test this behavior. **Cancel** closes the window without changes.

Diagnostics are stored in `%LOCALAPPDATA%\DipTraceSchPluginAdapter\<plugin_id>\captures`. The `latest.json` file in that directory points to the most recent run folder.

## Write your own plugin

### 1. Create a scaffold with your plugin's name

From the repository root, run:

```powershell
py -3 tools/new_plugin.py D:\PluginBuild\ProjectInfo --name ProjectInfo --mode job
```

Continue working in **`D:\PluginBuild\ProjectInfo`**. Edit its `plugin.py`; you do not need to modify the adapter repository's `examples` files. Do not run the scaffolding tool again for the same destination folder.

### 2. Replace the demonstration code with your implementation

For example, the following complete `plugin.py` creates `Docs\project-info.json` in the project directory:

```python
import json


def main(ctx):
    project_dir = ctx.project_dir
    if project_dir is None:
        raise ValueError("DipTrace did not provide a project directory")
    if not project_dir.is_dir():
        raise ValueError(f"Project directory does not exist: {project_dir}")

    variables = ctx.environment(["projectname", "revision", "Company"])
    output_dir = project_dir / "Docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "project-info.json"

    data = {
        "projectname": variables.get("projectname", ""),
        "revision": variables.get("revision", ""),
        "company": variables.get("company", ""),
    }
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ctx.log(f"Created {output_path}")
```

The adapter calls `main(ctx)` and supplies the context for the current invocation. You do not need to construct `ctx` or add a `main()` call at the bottom of the file. Running `python plugin.py` directly only defines the function; it does not execute the task.

This example writes missing variables as empty strings and **overwrites** `project-info.json` on subsequent runs. Add your own required-value checks or filename rules as needed.

`ctx.environment()` returns normalized keys: for `Company`, read `variables["company"]`. Use `ctx.document()` to get the schematic XML and process it with the standard `xml.etree.ElementTree` module.

### 3. Add your modules and resources

Place supporting `.py` files, templates, and configuration files beside `plugin.py` or in subdirectories. Resolve paths using `ctx.plugin_dir`, `ctx.project_dir`, and `ctx.run_dir` instead of assuming a particular process working directory.

Install third-party Python packages separately **into the interpreter specified in `adapter.ini`**. The adapter does not install dependencies at startup. If your plugin needs additional packages, include a `requirements.txt` file and installation instructions.

In `settings.xml`, you can edit the `Name` and `Hint` attributes of `Source` to set the user-facing name and description. `ExeFile` must match the EXE filename. Keep `mode` in the INI consistent with `ExpMode`/`ImpMode` in the XML.

### 4. Run your code

Copy the `ProjectInfo` folder into DipTrace as described in the quick start, then run the plugin from a saved project. Check `Docs\project-info.json` and the diagnostics.

During development, update the files **in the installed copy of the plugin** before the next run. Editing only `D:\PluginBuild\ProjectInfo\plugin.py` does not update the copy already installed under `Plugins\Schematic`.

### 5. Add schematic editing and a UI if needed

Create a scaffold with `--mode ui` and use the generated `plugin.py` as a reference for **Apply/Cancel** handlers:

1. At the start of `main(ctx)`, read `document = ctx.document()`.
2. Build your interface and run its event loop inside `main()`.
3. In the **Apply** handler, validate the input and modify `document`.
4. Call `ctx.commit_xml(document)`. If it succeeds, close the window so that `main()` can finish.
5. In the **Cancel** handler, call `ctx.cancel()` and close the window.

`commit_xml()` stages the result. DipTrace imports it after `main()` completes successfully and the adapter exits. Calling `commit_xml()` does not immediately update the open schematic.

The default `write_scope = sheet_settings` permits changes only within `/Source/Schematic/SheetSettings`, including title blocks. Editing components or other parts of the XML requires `write_scope = full`. Return the **complete document**, preserving nodes and attributes unrelated to your changes.

### 6. Package your plugin

A plugin package includes its EXE, `.adapter`, `adapter.ini`, `settings.xml`, `adapter.lock.json`, your Python code, and any required resources. You do not need to copy the adapter's C source, tests, or build tools into the installed plugin. Retain the license notices copied by the scaffolding tool.

Document the plugin's Python requirements, additional dependencies, installation steps, and expected output. For reproducible releases, pin the adapter commit as described below.

## Configure `adapter.ini`

Example configuration for a UI plugin:

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

| Setting | Meaning |
| --- | --- |
| `api_version` | `1` for this release. |
| `plugin_id` | The plugin identifier, also used for its separate diagnostics directory. |
| `mode` | `job` or `ui`. |
| `write_scope` | `sheet_settings` or `full`; returning changes is available only in `ui` mode. |
| `capture_dir` | Leave empty to use the default diagnostics directory. Relative paths are resolved against the plugin folder. |
| `executable` | `pyw.exe` or the absolute path to the required Python executable. |
| `entry` | The Python file containing `main(ctx)`; relative paths are resolved against the plugin folder. |

INI files support UTF-8 with or without a BOM, and UTF-16LE with a BOM. Put comments on separate lines.

## Plugin API

| Method or property | Purpose |
| --- | --- |
| `ctx.exchange_path` | Path to the captured XML. Do not modify this file. |
| `ctx.read_xml()` | Original XML bytes, checked against the capture hash. |
| `ctx.document()` | A fresh `ElementTree` root parsed from the XML, preserving comments and unknown nodes. |
| `ctx.project_dir` | A `Path` from `ProjectDir` in the XML, or `None`. |
| `ctx.plugin_dir` | The installed plugin directory. |
| `ctx.run_dir` | The diagnostics directory for this invocation. |
| `ctx.plugin_id`, `ctx.mode` | The identifier and mode of this invocation. |
| `ctx.environment(names)` | A dictionary of requested inherited variables with case-insensitive normalized keys. Missing variables are omitted. |
| `ctx.commit_xml(bytes_or_root)` | Stage a complete XML document for return; `ui` only. |
| `ctx.cancel()` | Discard a staged result. |
| `ctx.log(message)` | Append a message to `plugin.log`. |

`main()` returns `None` or `0`. An exception or nonzero return value discards the staged XML. Returning without `commit_xml()` also leaves the schematic unchanged. This applies to the schematic exchange; files created by the plugin itself are not automatically rolled back.

API 1 requires `ExpMode=All` and `ImpMode=All` for `ui`. Returning partial updates for individual objects is not supported. See [API and lifecycle](docs/API.md).

### Environment variables

`ctx.environment(["author", "Company"])` reads selected values from the **child process environment** inherited at startup. It does not read persistent Windows system settings. Names can be provided directly or wrapped as `<author>` or `%author%`.

This method **does not create or edit** variables in DipTrace's **Tools > Environment variables**. The `selected_environment.json` snapshot contains only requested variables that were found. During manual replay, the API does not automatically substitute this snapshot for the current process environment.

## Use the adapter repository as a dependency

You can maintain your plugin code in a separate repository. Pin the adapter to a specific commit and record it in `adapter.lock.json`; the plugin does not need to download the adapter every time it runs.

`new_plugin.py` creates a **new** plugin from the current local adapter checkout. `vendor_adapter.py` installs or updates **only the adapter dependency** in an existing plugin folder.

From the root of the cloned adapter repository, for the previously created `ProjectInfo`:

```powershell
$adapterCommit = (git rev-parse HEAD).Trim()
py -3 tools/vendor_adapter.py --repo https://github.com/steppefort/DipTraceSchPluginAdapter.git --commit $adapterCommit --dest D:\PluginBuild\ProjectInfo --exe ProjectInfo.exe
```

The selected commit must be available in the specified repository and contain `dist/DipTraceSchPluginAdapter.exe`. To update, select a verified commit for the desired release and pass its full 40-character SHA to `--commit`. The tool does not accept moving branch names such as `main`.

The tool fetches that exact commit, verifies its SHA, copies the EXE and Python runtime modules, and updates `adapter.lock.json`. It leaves your `plugin.py`, INI files, `settings.xml`, and templates unchanged. Specify the plugin's current EXE filename to keep it consistent with `settings.xml`.

Before updating an installed copy, stop any running plugin processes; the script does not stop them for you. The previous runtime modules are retained in `.adapter.previous`, which is not a complete plugin backup.

You can also keep the dependency as a Git submodule and run its tools when preparing a release. Distribute the complete plugin folder with its runtime modules so that the installed plugin needs neither Git nor a network connection.

## Debug without launching the EXE

You can run the Python side manually with a copy of XML captured from DipTrace. For example, for `ProjectInfo`:

```powershell
py -3 D:\PluginBuild\ProjectInfo\.adapter\host.py --config D:\PluginBuild\ProjectInfo\adapter.ini --exchange D:\PluginBuild\exchange-test.xml
```

First create `exchange-test.xml` as a **copy** of the XML from the capture you want to test. In `ui` mode, this file may be replaced with the result. This checks the Python code and file exchange, but does not update an open DipTrace schematic or test the native EXE.

Project variables are not automatically available during a manual run. For testing, set the required values in the current PowerShell session before running the command:

```powershell
$env:projectname = 'ExampleProject'
$env:revision = '1'
$env:Company = 'Example Company'
```

In `job` mode, the command may return before the task finishes. Check `status.json` in the new capture directory. UI plugins require a graphical environment and their chosen GUI toolkit.

## Build the adapter and run tests

This step is needed if you change `native/launcher.c` or want to build the EXE yourself. For an ordinary Python plugin, use the prebuilt file in `dist`.

From the repository root in PowerShell:

```powershell
py -3 -m pip install ziglang==0.14.1
$adapterZig = (py -3 -c "import pathlib, ziglang; print(pathlib.Path(ziglang.__file__).parent / 'zig.exe')").Trim()
py -3 tools/build.py --zig $adapterZig
py -3 -m unittest discover -s tests -v
```

On Linux, you can cross-compile the same Windows x64 EXE:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ziglang==0.14.1
adapter_zig="$(python -c 'import pathlib, ziglang; print(pathlib.Path(ziglang.__file__).parent / "zig")')"
python tools/build.py --zig "$adapter_zig"
python -m unittest discover -s tests -v
```

The build produces **`dist/DipTraceSchPluginAdapter.exe`**. The script verifies the PE x64 format and Windows GUI subsystem. Building the adapter does not automatically update existing plugin folders.

To create a plugin folder on Linux, use a command such as `python tools/new_plugin.py ./build/MyPlugin --name MyPlugin --mode job`. The resulting plugin is also intended for installation on Windows.

The repository includes a GitHub Actions workflow for builds and tests on Linux and Windows. The native launch test runs only on Windows. These checks do not replace testing the installed plugin directly in DipTrace.

## Adapt an existing plugin

The basic migration steps are:

1. Create a new folder with `new_plugin.py` in the appropriate mode.
2. Copy in the existing plugin's application code, templates, and configuration files.
3. Implement `main(ctx)` and use `ctx.read_xml()` or `ctx.document()` to read the input XML.
4. For an editor, submit the complete modified XML through `ctx.commit_xml()` after the user confirms the changes.
5. Check the result in DipTrace and package the entire folder.

The [BOMJob bridge](examples/bomjob_bridge/plugin.py) demonstrates calling the existing BOMJob 0.2.7 worker. Place the bridge as `plugin.py` beside the BOMJob modules, retain `bomjob.ini` and the templates, and use `mode=job` with `ImpMode=None`.

The [UI example](examples/ui/plugin.py) demonstrates title-block editing. A full template or environment-variable editor needs its own implementation. See the [migration notes (Russian)](docs/MIGRATION.md) for additional guidance.

## Diagnostics

Each invocation gets a separate subdirectory under `%LOCALAPPDATA%\DipTraceSchPluginAdapter\<plugin_id>\captures`, unless `capture_dir` overrides the location.

| File | Purpose |
| --- | --- |
| `context.json` | Parameters for this invocation. |
| `exchange.xml` | The immutable original XML capture. |
| `status.json` | Execution status: `starting`, `ok`, `changed`, `cancelled`, or `error`. |
| `worker.log` | Standard output and standard error from the Python process. |
| `plugin.log` | Messages from `ctx.log()` and any execution errors. |
| `selected_environment.json` | Available variables explicitly requested through the API. |
| `result.xml` | Staged modified XML, if `commit_xml()` was called. |
| `applied.json` | Confirmation that the result was written to the exchange file. |

Not every file is created on every run. `changed` means a result has been staged; writing it to the original exchange file is separately recorded in `applied.json`. For initial startup errors, also check `%LOCALAPPDATA%\DipTraceSchPluginAdapter\last_error.log`.

Automatic capture cleanup is not implemented. Captures may contain project data and selected variable values. The API checks the scope of XML changes, but is not a sandbox: plugin Python code runs with the user's permissions.

## References and license

- [Adapter API](docs/API.md).
- [Migration guide](docs/MIGRATION.md).
- [Official DipTrace documentation and SDK](https://diptrace.com/support/tutorials/).
- [DipTrace plugin specification](https://diptrace.com/books/DipTrace_Plugins.pdf).
- [MIT license](LICENSE) and [third-party notices](THIRD_PARTY.md).

The official DipTrace SDK is not distributed in this repository. DipTrace is a Novarm product; DipTraceSchPluginAdapter is an independent community project.
