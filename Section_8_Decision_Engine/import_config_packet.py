# ======================================================
# ENGINE INPUT: INPUTS / CONFIGURATION PACKET
# ======================================================
# Shared by all scoring engines.
#
# This file is responsible ONLY for importing the
# stable InputsPacket contract from Section 2.
#
# It contains NO configuration calculation logic.
# ======================================================

from Section_2_Inputs.inputs_packet import (
    InputsPacket,
    create_inputs_packet,
)

__all__ = [
    "InputsPacket",
    "create_inputs_packet",
]