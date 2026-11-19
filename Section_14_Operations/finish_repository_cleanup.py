"""Finish the folder-cleanup merge while retaining local state and saved edits."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import subprocess
import sys

RUNTIME = ('Section_1_Global_Core/section_1_9_state.json', 'Section_1_Global_Core/Symbols/symbols.json')
REPORT = 'research_reports/BTC_1h_sequences/strategy_analyzer/strategy_analysis.json.gz'
TARGET = 'origin/chore/separate-app-research-tools'


def git(root, *args, check=True):
    return subprocess.run(['git', *args], cwd=root, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def changed(root, *revisions):
    return [p for p in git(root, 'diff', '--name-only', '-z', *revisions).stdout.decode().split('\0') if p]


def report_stash(root):
    for line in git(root, 'stash', 'list', '--format=%H%x09%gs').stdout.decode().splitlines():
        identity, message = line.split('\t', 1)
        if message.endswith(': report-before-cleanup'):
            return identity
    raise RuntimeError('The report-before-cleanup stash was not found. No files changed.')


def mapped_patch(root, stash, moves):
    files = changed(root, stash+'^1', stash)
    selected = [p for p in files if p == REPORT or p.startswith('tests/')]
    untouched = [p for p in files if p not in selected]
    if not selected:
        return b'', selected, untouched
    patch = git(root, 'diff', '--binary', '--no-renames', stash+'^1', stash, '--', *selected).stdout
    result = []
    for line in patch.splitlines(keepends=True):
        if line.startswith((b'diff --git ', b'--- a/', b'+++ b/')):
            for old in selected:
                new = moves.get(old, 'Section_13_Development/'+old if old.startswith('tests/') else old)
                for prefix in (b'a/', b'b/'):
                    line = line.replace(prefix+old.encode(), prefix+new.encode())
        result.append(line)
    return b''.join(result), selected, untouched


def finish(root, target, stash, *, stop_services):
    root = Path(root).resolve()
    if git(root, 'rev-parse', '-q', '--verify', 'MERGE_HEAD', check=False).returncode == 0:
        raise RuntimeError('A merge is already active. No files changed; send git status output.')
    dirty = changed(root, 'HEAD')
    other = [p for p in dirty if p not in RUNTIME]
    if other:
        raise RuntimeError('Additional local edits need review; nothing changed: '+', '.join(other))
    document = json.loads(git(root, 'show', target+':Section_13_Development/repository_layout/moves.json').stdout)
    patch, selected, untouched = mapped_patch(root, stash, {m['old']:m['new'] for m in document['moves']})
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root.parent / (root.name+'-cleanup-backups') / stamp
    backup.mkdir(parents=True, mode=0o700)
    (backup/'saved-edits.patch').write_bytes(patch)
    (backup/'stash-id.txt').write_text(stash+'\n')
    (backup/'local-before.patch').write_bytes(git(root, 'diff', '--binary', 'HEAD').stdout)
    print('Recovery backup:', backup, flush=True)
    saved = {}
    with stop_services():
        # Capture state only once its owning writers have stopped.
        other = [p for p in changed(root, 'HEAD') if p not in RUNTIME]
        if other:
            raise RuntimeError('New local edits appeared; merge not started: '+', '.join(other))
        for name in RUNTIME:
            path = root/name
            if path.is_file():
                saved[name] = path.read_bytes()
                destination = backup/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(saved[name])
        try:
            if saved:
                git(root, 'restore', '--source=HEAD', '--staged', '--worktree', '--', *saved)
            result = git(root, '-c', 'merge.autoStash=false', 'merge', '--no-ff', '--no-commit', target, check=False)
            if result.returncode:
                if git(root, 'rev-parse', '-q', '--verify', 'MERGE_HEAD', check=False).returncode == 0:
                    git(root, 'merge', '--abort')
                raise RuntimeError('Cleanup merge stopped; saved edits were not applied.\n'+result.stderr.decode())
            if any(p.startswith('Section_11_UI_UX/') for p in changed(root, '--cached')):
                git(root, 'merge', '--abort')
                raise RuntimeError('The merge would change UI/UX files; it was aborted. Current UI preserved.')
            if git(root, 'rev-parse', '-q', '--verify', 'MERGE_HEAD', check=False).returncode == 0:
                git(root, 'commit', '--no-edit')
            if patch:
                patch_path = backup/'saved-edits.patch'
                result = git(root, 'apply', '--3way', str(patch_path), check=False)
                if result.returncode:
                    raise RuntimeError('Cleanup merged, but saved test/report edits need conflict review. '
                                       'Stash and backup retained. Send git status output.\n'+result.stderr.decode())
            print('Cleanup merged. Restored saved test/report paths:', len(selected), flush=True)
            if untouched:
                print('Other saved paths left untouched in the original stash:', ', '.join(untouched), flush=True)
            print('All original stashes retained. UI/UX unchanged.', flush=True)
        finally:
            for name, data in saved.items():
                (root/name).write_bytes(data)
            print('Latest local runtime state restored.', flush=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').stdout.decode().strip())
    stash = report_stash(root)
    if not args.apply:
        print(json.dumps(dict(checkout=str(root), target=TARGET, report_stash=stash,
                             local_changes=changed(root, 'HEAD'), apply=False), indent=2))
        return
    sys.path.insert(0, str(root))
    # Reuse the existing, tested service ownership checks and restart-on-error guard.
    module = 'compact_feature_storage' if (root/'compact_feature_storage.py').is_file() else 'Section_14_Operations.storage.compact_feature_storage'
    services = importlib.import_module(module)
    finish(root, TARGET, stash, stop_services=services.stopped_services)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        message = ((error.stderr or b'').decode() or str(error)) if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise SystemExit(message)
