# Changelog

English · [Українська](CHANGELOG_UA.md)

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
