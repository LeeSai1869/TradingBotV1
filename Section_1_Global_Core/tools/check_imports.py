# ============================================================
# tools/check_imports.py
# Public-surface enforcer for Global Core.
# ============================================================
#
# Rule:
#   Strategy consumers outside Section_1_Global_Core/ may import ONLY
#   the following from Global Core:
#
#       Section_1_Global_Core.global_packet
#       Section_1_Global_Core.import_*_packet
#       Section_1_Global_Core.Data_Contracts_Legacy.constants
#       Section_1_Global_Core.Data_Contracts_Legacy.market_definitions
#       Section_1_Global_Core.Data_Contracts_Legacy.market_state
#       Section_1_Global_Core.Data_Contracts_Legacy.memory
#       Section_1_Global_Core.Data_Contracts_Legacy.timeframes
#       Section_1_Global_Core.Data_Contracts_Legacy.outputs
#       Section_1_Global_Core.Data_Contracts_Legacy.global_state
#       Section_1_Global_Core.Symbols.symbols
#
# Reviewed worker/UI/diagnostic bridges have exact grants in integration_imports.json.
# Integration tests may inspect internals; retired Section 6/7 imports are always rejected.
# Anything else (in particular, anything under
# Section_1_Global_Core.memory_storage.*)
# is PRIVATE and must not be imported from outside.
#
# Usage:
#   python3 -m Section_1_Global_Core.tools.check_imports
# ============================================================

from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_CORE = PROJECT_ROOT / "Section_1_Global_Core"

_INTEGRATIONS_FILE = GLOBAL_CORE / "tools" / "integration_imports.json"


def _load_integrations() -> set[tuple[str,str]]:
    import json
    if not _INTEGRATIONS_FILE.exists():return set()
    doc=json.loads(_INTEGRATIONS_FILE.read_text())
    return {(file,module) for file,modules in doc.get('integrations',{}).items() for module in modules}


ALLOWED_TOP_LEVEL = {
    # The socket — every downstream section imports packets through here
    "Section_1_Global_Core.Imports.import_features_packet",
    "Section_1_Global_Core.Imports.import_regime_packet",
    "Section_1_Global_Core.Imports.import_opportunity_score",
    "Section_1_Global_Core.Imports.import_confidence_score",
    "Section_1_Global_Core.Imports.import_scalp_decision_score_packet",
    # The public gateway
    "Section_1_Global_Core.global_packet",
    "Section_1_Global_Core.tools.audit_status",
    "Section_1_Global_Core.import_features_packet",
    "Section_1_Global_Core.import_regime_packet",
    "Section_1_Global_Core.import_opportunity_score",
    "Section_1_Global_Core.import_confidence_score",
    "Section_1_Global_Core.import_scalp_decision_score_packet",
    "Section_1_Global_Core.Data_Contracts_Legacy.constants",
    "Section_1_Global_Core.Data_Contracts_Legacy.market_definitions",
    "Section_1_Global_Core.Data_Contracts_Legacy.market_state",
    "Section_1_Global_Core.Data_Contracts_Legacy.memory",
    "Section_1_Global_Core.Data_Contracts_Legacy.timeframes",
    "Section_1_Global_Core.Data_Contracts_Legacy.outputs",
    "Section_1_Global_Core.Data_Contracts_Legacy.global_state",
    "Section_1_Global_Core.Symbols.symbols",
}


def _is_allowed(module: str) -> bool:
    if module in ALLOWED_TOP_LEVEL:
        return True
    # Allow any submodule of an allowed module (e.g. `.Data_Contracts_Legacy.constants.thing`)
    for allowed in ALLOWED_TOP_LEVEL:
        if module.startswith(allowed + "."):
            return True
    return False


def _imports_of(path: Path) -> set[str]:
    """Return set of fully-qualified module names imported at any depth."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return set()

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                found.add(name.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module)
                # also record from-imports of the form:
                #   from Section_1_Global_Core.memory_storage import X
                # as module path Section_1_Global_Core.memory_storage
    return found


def scan() -> int:
    violations: list[tuple[Path, str]] = []

    for py in PROJECT_ROOT.rglob("*.py"):
        # Retired engines must not return through any runtime or test import.
        for module in _imports_of(py):
            if module.startswith(('Section_6_Base_Scoring_Engines','Section_7_Confluence_Engines')):
                violations.append((py,module))
        # Integration tests intentionally inspect internal stores and fixtures.
        if py.relative_to(PROJECT_ROOT).parts[0]=='tests':continue
        # skip Global Core itself, .venv, and caches
        try:
            py.relative_to(GLOBAL_CORE)
            continue
        except ValueError:
            pass
        if ".venv" in py.parts or "__pycache__" in py.parts:
            continue

        for mod in _imports_of(py):
            if mod.startswith("Section_1_Global_Core"):
                if not _is_allowed(mod):
                    violations.append((py, mod))

    integrations = _load_integrations()

    allowed_by_rule = []
    new_violations = []
    for path, mod in violations:
        rel_str = str(path.relative_to(PROJECT_ROOT))
        if (rel_str, mod) in integrations:
            allowed_by_rule.append((rel_str, mod))
        else:
            new_violations.append((rel_str, mod))

    if allowed_by_rule:
        print(f"Reviewed integrations ({len(allowed_by_rule)}):")
        for rel, mod in sorted(allowed_by_rule):
            print(f"  {rel}: {mod}")
        print()

    if not new_violations:
        print("OK — public boundary and reviewed integration imports respected.")
        return 0

    print("NEW VIOLATIONS FOUND:")
    for rel, mod in new_violations:
        print(f"  {rel}: imports private module {mod}")
    print()
    print(f"Total NEW violations: {len(new_violations)}")
    return 1


if __name__ == "__main__":
    sys.exit(scan())
