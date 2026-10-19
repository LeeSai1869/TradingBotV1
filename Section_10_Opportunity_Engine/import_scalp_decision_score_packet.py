# ======================================================
# IMPORT: SCALP DECISION SCORE PACKET
# ======================================================

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PACKET_FILE = (
    PROJECT_ROOT
    / "Section_8_ Decision_Engine"
    / "section_8.1_Scalp_Decision"
    / "scalp_decision_score_packet.py"
)


_spec = importlib.util.spec_from_file_location(
    "scalp_decision_score_packet_module",
    PACKET_FILE,
)

if _spec is None or _spec.loader is None:
    raise ImportError(
        f"Unable to load ScalpDCNScorePacket from: {PACKET_FILE}"
    )


_module = importlib.util.module_from_spec(_spec)

_spec.loader.exec_module(_module)


ScalpDCNScorePacket = _module.ScalpDCNScorePacket