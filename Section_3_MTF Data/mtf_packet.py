from dataclasses import dataclass
from typing import Optional, Dict

import importlib.util
from pathlib import Path


# ---------------------------------------------------------
# Load the existing MTF Data module
# ---------------------------------------------------------

MTF_FILE = Path(__file__).parent / "MTF Data.py"

_spec = importlib.util.spec_from_file_location(
    "mtf_data_module",
    MTF_FILE
)

mtf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mtf)


# ---------------------------------------------------------
# MTF PACKET
# ---------------------------------------------------------

@dataclass
class MTFPacket:

    # -----------------------------------------------------
    # Timeframe
    # -----------------------------------------------------

    tf: str

    # -----------------------------------------------------
    # Current OHLC
    # -----------------------------------------------------

    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]

    # -----------------------------------------------------
    # Previous OHLC
    # -----------------------------------------------------

    prev_open: Optional[float]
    prev_high: Optional[float]
    prev_low: Optional[float]
    prev_close: Optional[float]

    # -----------------------------------------------------
    # Volume
    # -----------------------------------------------------

    volume: Optional[float]
    prev_volume: Optional[float]
    volume_ma: Optional[float]

    # -----------------------------------------------------
    # Time / bar information
    # -----------------------------------------------------

    time: Optional[int]
    prev_time: Optional[int]

    bar_index: Optional[int]
    prev_bar_index: Optional[int]

    # -----------------------------------------------------
    # Price
    # -----------------------------------------------------

    current_price: Optional[float]

    # -----------------------------------------------------
    # Derived price values
    # -----------------------------------------------------

    vwap: Optional[float]
    hl2: Optional[float]
    hlc3: Optional[float]
    ohlc4: Optional[float]

    # -----------------------------------------------------
    # EMA
    # -----------------------------------------------------

    ema7: Optional[float]
    ema25: Optional[float]
    ema50: Optional[float]
    ema100: Optional[float]
    ema200: Optional[float]
    ema300: Optional[float]

    # -----------------------------------------------------
    # Previous EMA
    # -----------------------------------------------------

    prev_ema7: Optional[float]
    prev_ema25: Optional[float]
    prev_ema50: Optional[float]
    prev_ema100: Optional[float]
    prev_ema200: Optional[float]
    prev_ema300: Optional[float]

    # -----------------------------------------------------
    # WMA
    # -----------------------------------------------------

    wma50: Optional[float]


# ---------------------------------------------------------
# CONVERT EXISTING MTF DATA → MTF PACKET
# ---------------------------------------------------------

def create_mtf_packet(tf: str) -> Optional[MTFPacket]:

    data = mtf.get_mtf_data(tf)

    if data is None:
        return None

    return MTFPacket(

        tf=data.tf,

        open=data.open,
        high=data.high,
        low=data.low,
        close=data.close,

        prev_open=data.prev_open,
        prev_high=data.prev_high,
        prev_low=data.prev_low,
        prev_close=data.prev_close,

        volume=data.volume,
        prev_volume=data.prev_volume,
        volume_ma=data.volume_ma,

        time=data.time,
        prev_time=data.prev_time,

        bar_index=data.bar_index,
        prev_bar_index=data.prev_bar_index,

        current_price=data.current_price,

        vwap=data.vwap,
        hl2=data.hl2,
        hlc3=data.hlc3,
        ohlc4=data.ohlc4,

        ema7=data.ema7,
        ema25=data.ema25,
        ema50=data.ema50,
        ema100=data.ema100,
        ema200=data.ema200,
        ema300=data.ema300,

        prev_ema7=data.prev_ema7,
        prev_ema25=data.prev_ema25,
        prev_ema50=data.prev_ema50,
        prev_ema100=data.prev_ema100,
        prev_ema200=data.prev_ema200,
        prev_ema300=data.prev_ema300,

        wma50=data.wma50,
    )


# ---------------------------------------------------------
# CREATE PACKETS FOR ALL REQUIRED TIMEFRAMES
# ---------------------------------------------------------

def create_all_mtf_packets() -> Dict[str, MTFPacket]:

    packets: Dict[str, MTFPacket] = {}

    for tf in mtf.required_tf_registry:

        packet = create_mtf_packet(tf)

        if packet is not None:
            packets[tf] = packet

    return packets