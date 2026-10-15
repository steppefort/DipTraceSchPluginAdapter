# Changelog

English · [Українська](CHANGELOG_UA.md)

## 0.1.2

- Allow `ImpMode=Edit` as well as `All` in `ui` mode while preserving API 1,
  full-document `ctx.commit_xml()` and `write_scope=sheet_settings`.
- Advance the exchange XML modification time by at least two seconds when a
  changed result is published; leave the file untouched for no-op results.
- Detect external rewrites of the exchange XML by checking its modification
  time and size in addition to the SHA-256 content hash.
- Supervise UI Python processes through a Windows Job Object to prevent
  orphaned workers; retain independent background execution in `job` mode.
- Add a `--profile stamp` generator preset with `ImpMode=Edit`, `Stamp=Yes`,
  `Patterns=No` and other import categories disabled.
- Extend regression tests and update English/Ukrainian integration guides.

API remains 1. TitleJob's existing frame-import transformation is unchanged.

## 0.1.1

- Resolve bare Python executable names through PATH before CreateProcessW.
- Pass the Python launcher selector `-3` without quotes.
- Record native startup commands, Python output and process failures in TEMP.
- Generate version metadata from `build_info.json` for Python, EXE file
  properties, dialogs, logs and dependency locks.
- Add `--version`, versioned release archives and checks for stale builds.
- Add optional independent plugin versions to generated DipTrace display names.

API remains 1. Existing `main(ctx)` plugins remain compatible.

## 0.1.0

Initial shared adapter with job/UI modes, transactional XML return,
Python context API, plugin generation and commit-pinned vendoring.
