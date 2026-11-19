# Operations

Explicit commands for services, accounts, configuration and storage maintenance.
Run from the repository root; prefer Python's module form:

```sh
python3 -m Section_14_Operations.services.restart_ui
python3 -m Section_14_Operations.storage.compact_feature_storage --status
python3 -m Section_14_Operations.storage.retire_atr_slope_storage --status
```

Installed chart and runner module names, launchd labels and launcher paths remain
unchanged. Existing LaunchAgents do not need to be reinstalled for this move.
Market databases, checkpoints and private settings remain at their existing paths.

## Local files left after pulling

Git moves tracked files. Ignored local reports and backups on an existing Mac
need a separate pass. Preview the known research folders and root code backups:

```sh
python3 -m Section_14_Operations.organize_local_files
```

Move only the listed files:

```sh
python3 -m Section_14_Operations.organize_local_files --apply
```

This archives files rather than deleting them. Conflicting reports go to
`Section_13_Development/local_archive/`; committed destinations are never
replaced. Move records are saved there. Databases and their sidecars, secrets,
symlinks, virtual environments and tracked files are excluded. Unknown files are
left for review. Do not rerun database retirement or compaction to organize files.

## Recover a blocked cleanup merge

`finish_repository_cleanup.py --apply` is for the interrupted report-before-cleanup
workflow. It uses the existing launchd ownership checks to pause and resume chart
and runner services. It saves current state outside the app, merges the cleanup
with autostash disabled, and maps saved report/test edits to their new paths.
All original stashes and the recovery patch are retained. Runtime state from an
older stash is never restored over the latest checkpoint. A merge that would
change UI/UX files is aborted. Unexpected local code edits stop the operation
before the merge; test/report patch conflicts are left for review with backups.

Before the branch is installed, extract the recovery command from the fetched
branch into `/tmp` and run it from the original application checkout. Afterward,
use the organizer for the `.py.before-slope-*` backup files. Keep
`features.db.compaction.json` beside the database; maintenance checks use it.
