"""Section 1 — Audit layer.

Public API:
    from ...Audit import audit_runner
    manifest = audit_runner.run()            # full run, respects config
    manifest = audit_runner.run_fast()       # A1 + A2 + A5 only

Individual checks:
    from ...Audit import audit_schema, audit_continuity, ...
    audit_schema.run(rows=[...])             # or
    audit_schema.run(symbol=..., interval=...)
"""
