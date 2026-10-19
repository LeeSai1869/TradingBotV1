from pathlib import Path
import importlib.util


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PACKET_FILE = (
    PROJECT_ROOT
    / "2_ Inputs"
    / "inputs_packet.py"
).resolve()


spec = importlib.util.spec_from_file_location(
    "inputs_packet_module",
    PACKET_FILE
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

InputsPacket = module.InputsPacket