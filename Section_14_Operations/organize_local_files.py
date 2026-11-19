"""Archive local research/build leftovers without touching market data or secrets."""
from __future__ import annotations

if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import fnmatch
from pathlib import Path
import subprocess
from Section_1_Global_Core.paths import REPO_ROOT

FOLDERS = {
    'research_reports': 'Section_12_Research/reports',
    'research_ui': 'Section_12_Research/ui',
    'research_fixes': 'Section_12_Research/fixes',
    'tests': 'Section_13_Development/local_archive/tests',
}
CODE_BACKUP_MARKERS = tuple(suffix+'.before-' for suffix in ('.py','.js','.mjs','.ts','.tsx','.sh'))
PROTECTED = {'.git', '.venv', '.venv-build', 'venv', 'node_modules', '__pycache__', '.agents', '.codex'}


def protected(path):
    name = path.name.lower()
    return (any(p in PROTECTED for p in path.parts) or path.is_symlink()
            or any(s in name for s in ('.db', '.sqlite', '.env', 'password', 'credential', 'secret', 'service-account'))
            or path.suffix.lower() in {'.pem', '.key', '.keystore', '.jks'})


def plan(root):
    root = Path(root).resolve()
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0'))
    moves = []
    for old, new in FOLDERS.items():
        directory = root / old
        if not directory.is_dir() or directory.is_symlink():
            continue
        for source in sorted(directory.rglob('*')):
            if not source.is_file() or protected(source) or any(p.is_symlink() for p in source.parents):
                continue
            relative = source.relative_to(root).as_posix()
            if relative in tracked:
                continue
            target = root / new / source.relative_to(directory)
            # A locally edited report must never overwrite the committed copy.
            if target.exists():
                target = root / 'Section_13_Development/local_archive' / relative
            if target.exists() or target.is_symlink():
                continue
            moves.append((source, target))
    runtime = [d for d in root.glob('Section_*') if d.is_dir() and not d.is_symlink() and d.name.split('_')[1].isdigit() and int(d.name.split('_')[1]) <= 11]
    candidates = list(root.iterdir())
    for directory in runtime:
        candidates.extend(p for p in directory.rglob('*') if '.bak' in p.name or any(marker in p.name for marker in CODE_BACKUP_MARKERS) or p.name.endswith(('.backup', '.orig', '.rej', '.save')))
    for source in sorted(candidates):
        if (source.is_file() and not protected(source)
                and source.relative_to(root).as_posix() not in tracked
                and ('.bak' in source.name or any(marker in source.name for marker in CODE_BACKUP_MARKERS) or source.name.endswith(('.backup', '.orig', '.rej', '.save')) or (source.parent == root and any(fnmatch.fnmatch(source.name, pattern) for pattern in ('*_review.json','*_readiness.json','scalp_*bps.json','strategy_report.json'))))):
            target = root / 'Section_13_Development/local_archive' / ('root' if source.parent == root else '') / source.relative_to(root)
            if not target.exists() and not target.is_symlink():
                moves.append((source, target))
    return moves


def organize(root, *, apply=False):
    root = Path(root).resolve()
    moves = plan(root)
    record = {'apply': apply, 'moves': [{'from': str(a.relative_to(root)), 'to': str(b.relative_to(root))} for a,b in moves]}
    if apply:
        for source, target in moves:
            if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
                raise RuntimeError(f'Unsafe destination; retained {source}')
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        reports = root / 'Section_13_Development/local_archive'
        reports.mkdir(parents=True, exist_ok=True)
        import time
        (reports / f'moves-{time.time_ns()}.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Move listed files; default only previews')
    args = parser.parse_args()
    print(json.dumps(organize(REPO_ROOT, apply=args.apply), indent=2))


if __name__ == '__main__':
    main()
