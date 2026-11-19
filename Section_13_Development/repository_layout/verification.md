# Repository cleanup verification

Scope: reorganize tracked files from the original application checkout, record
moves, preserve local research files and update tool imports/resources. This
branch does not merge the separate chart-preview updates from `origin/main`.
The preview checkout remains independent.

## Preserved behavior and data

- All files under `Section_11_UI_UX` are byte-for-byte unchanged from application
  baseline `293c08d`. No UI, UX, chart-rendering or price behavior changes.
- Installed chart/runner launcher paths, launchd labels and module names stay
  unchanged. Databases, checkpoints, runtime policy and accounts keep their paths.
- 403 tracked moves are listed in `moves.json`, with original SHA-256 values.
  Frozen JSON/CSV/gzip/HTML reports and the Pine reference retain their bytes.
- The shared field catalog moved into the existing Decision Engine package so
  the application does not depend on Research, Development or Operations imports.
- Root contains the application entry point, README and required Git files;
  dependencies are under `packaging/requirements/`, documentation under `docs/`.

## Final checks

- 51 targeted Python checks passed: move/content invariants, runtime import
  boundaries, launchers, account recovery, compaction safeguards and research
  workspace/memory integration.
- 130 JavaScript checks passed.
- Signed-in browser checks passed for market switching/render recovery, live
  price and candle rollover, and settings/volume behavior.
- Exact public-import boundary check and Python compilation passed.
- Disposable Git worktree test passed: save only the locally edited compressed
  research report, merge the cleanup, then restore that edit at its renamed
  location. The independently modified runtime state remains untouched.

The broader 950-test sweep found five existing failures reproduced unchanged on
baseline `293c08d`: three reference-conversion checks depend on `kernels.py` and
`validate_export.py`, removed by earlier commit `d78a497`; the all-feature export
fixture enumerates physical rather than virtual columns; the volume-profile
fixture omits candle close required by the derived reader. These are recorded
rather than restoring retired tools or changing application behavior here.
Two additional failures in that first sweep were resolved: the moved import-test
fixture now creates its parent folder, and the environment's missing optional
`websocket-client` dependency was installed for recorder testing.

## Existing Mac checkout

Git cannot move an unstaged local report through a merge. Save that report alone
before merging this branch; restore it afterward. Do not stash, reset or overwrite
`symbols.json` or `section_1_9_state.json` for this cleanup. Their paths and contents
are unchanged by this branch. The tested report path is:

- Before: `research_reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz`
- After: `Section_12_Research/reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz`

For ignored local reports and conventional source backups, use
`python3 -m Section_14_Operations.organize_local_files` to preview and add `--apply`
to archive the listed files. See the Operations README for exclusions and records.
Restart existing chart/runner services after pulling to reload moved imports.
