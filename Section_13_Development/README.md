# Development

Tests, profiling, diagnostics and repository maintenance records live here.

```sh
python3 -m unittest discover -s Section_13_Development/tests -q
node --test Section_13_Development/tests/*.test.mjs Section_13_Development/tests/test_*.js
python3 -m Section_13_Development.diagnostics.core.check_imports
python3 -m Section_13_Development.diagnostics.profile_chart_loading --help
```

Run browser checks from the repository root, using a locally available chart
library if needed:

```sh
python3 -m Section_13_Development.tests.browser_live /tmp/lightweight-charts-5.2.1.js
```

`repository_layout/moves.json` records every tracked move and the original file's
SHA-256. Frozen research data and the Pine reference retain their original bytes.
`archive/root/` preserves the old root's stray files. `local_archive/` is ignored
by Git and holds machine-local files moved by the Operations organizer.
