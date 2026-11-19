"""Read-only audit details: python3 Section_13_Development/diagnostics/audit_status.py [--symbol ETHUSDT]."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

from Section_13_Development.diagnostics.core.audit_status import main

if __name__=='__main__':main()
