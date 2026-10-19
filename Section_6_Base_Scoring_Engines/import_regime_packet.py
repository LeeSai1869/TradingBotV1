# ======================================================
# ENGINE INPUT: REGIME PACKET
# ======================================================
# Shared by all scoring engines.
#
# This file is responsible ONLY for importing the
# stable RegimePacket contract from Section 5.
#
# It contains NO market-regime calculation logic.
# ======================================================

from Section_5_Market_Regime.regime_packet import RegimePacket


__all__ = [
    "RegimePacket",
]