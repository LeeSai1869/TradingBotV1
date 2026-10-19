# ======================================================
# MARKET LIQUIDITY
# Full Dynamic + Institutional Liquidity Detection
# Faithful translation of original Pine Script logic
#
# IMPORTANT:
# - This module is independent from Support & Resistance.
# - It does not modify MarketLevels or SRMemory.
# - SweepDetected = liquidity event only.
# - SweepReclaim / SweepReject = confirmation.
# - No scoring-engine logic is performed here.
# ======================================================

from dataclasses import dataclass
from typing import Optional, Dict, Any
import math

import numpy as np


# ======================================================
# LIQUIDITY OUTPUT CONTRACT
# ======================================================

@dataclass
class MarketLiquidity:

    # --------------------------------------------------
    # Recent swing liquidity
    # --------------------------------------------------

    liquidity_high: Optional[float] = None
    liquidity_low: Optional[float] = None

    liquidity_high_distance: Optional[float] = None
    liquidity_low_distance: Optional[float] = None

    prev_low_liquidity: Optional[float] = None
    prev_high_liquidity: Optional[float] = None

    # --------------------------------------------------
    # Equal highs / lows
    # --------------------------------------------------

    equal_high_liquidity: Optional[bool] = None
    equal_low_liquidity: Optional[bool] = None

    # --------------------------------------------------
    # Liquidity sweep context
    # --------------------------------------------------

    bull_sweep_detected: Optional[bool] = None
    bear_sweep_detected: Optional[bool] = None

    bull_sweep_reclaim: Optional[bool] = None
    bear_sweep_reject: Optional[bool] = None

    # --------------------------------------------------
    # Sweep strength
    # --------------------------------------------------

    bull_sweep_strength: Optional[float] = None
    bear_sweep_strength: Optional[float] = None

    # --------------------------------------------------
    # Absorption
    # --------------------------------------------------

    bid_absorption: bool = False
    ask_absorption: bool = False

    bid_absorption_strength: float = 0.0
    ask_absorption_strength: float = 0.0

    # --------------------------------------------------
    # Liquidity type
    # --------------------------------------------------

    liquidity_type: Optional[str] = None

    # --------------------------------------------------
    # External liquidity
    # --------------------------------------------------

    external_high_liquidity: Optional[float] = None
    external_low_liquidity: Optional[float] = None

    external_high_distance_pct: Optional[float] = None
    external_high_distance: Optional[float] = None

    external_low_distance_pct: Optional[float] = None
    external_low_distance: Optional[float] = None

    # --------------------------------------------------
    # Internal liquidity
    # --------------------------------------------------

    internal_high_liquidity: Optional[float] = None
    internal_low_liquidity: Optional[float] = None

    internal_high_distance_pct: Optional[float] = None
    internal_high_distance: Optional[float] = None

    internal_low_distance_pct: Optional[float] = None

    # --------------------------------------------------
    # Liquidity clusters
    # --------------------------------------------------

    high_cluster_count: int = 0
    low_cluster_count: int = 0

    high_liquidity_cluster_score: float = 0.0
    low_liquidity_cluster_score: float = 0.0

    high_liquidity_cluster: bool = False
    low_liquidity_cluster: bool = False

    # --------------------------------------------------
    # Liquidity age
    # --------------------------------------------------

    high_liquidity_age: Optional[int] = None
    low_liquidity_age: Optional[int] = None

    # --------------------------------------------------
    # Liquidity importance
    # --------------------------------------------------

    high_liquidity_importance: float = 0.0
    low_liquidity_importance: float = 0.0

    # --------------------------------------------------
    # Liquidity location
    # --------------------------------------------------

    liquidity_location: Optional[str] = None
    liquidity_side: Optional[str] = None

    # --------------------------------------------------
    # Nearest liquidity
    # --------------------------------------------------

    nearest_buy_liquidity_pct: Optional[float] = None
    nearest_sell_liquidity_pct: Optional[float] = None

    nearest_buy_liquidity_price: Optional[float] = None
    nearest_sell_liquidity_price: Optional[float] = None

    nearest_buy_liquidity_price_distance: Optional[float] = None
    nearest_sell_liquidity_price_distance: Optional[float] = None

    nearest_buy_liquidity_atr_distance: Optional[float] = None
    nearest_sell_liquidity_atr_distance: Optional[float] = None


# ======================================================
# LIQUIDITY MEMORY
# ======================================================
#
# The current Pine liquidity logic does not maintain a
# permanent zone object like Support/Resistance.
#
# Therefore no artificial persistent liquidity-zone memory
# is introduced here.
#
# The output is calculated from the supplied historical
# series exactly as the Pine block calculates it.
# ======================================================

@dataclass
class LiquidityMemory:
    """
    Reserved for future liquidity state that is explicitly
    present in the source logic.

    No additional persistent state is introduced because
    the supplied Pine liquidity block does not require it.
    """
    pass


_liquidity_memory_store: Dict[str, LiquidityMemory] = {}


def get_liquidity_memory(tf: str) -> LiquidityMemory:
    if tf not in _liquidity_memory_store:
        _liquidity_memory_store[tf] = LiquidityMemory()
    return _liquidity_memory_store[tf]


# ======================================================
# HELPERS
# ======================================================

def _pine_highest(
    values: Optional[np.ndarray],
    length: int
) -> Optional[float]:

    if values is None:
        return None

    if length <= 0:
        return None

    if len(values) < length:
        return None

    window = values[-length:]

    if np.isnan(window).all():
        return None

    return float(np.nanmax(window))


def _pine_lowest(
    values: Optional[np.ndarray],
    length: int
) -> Optional[float]:

    if values is None:
        return None

    if length <= 0:
        return None

    if len(values) < length:
        return None

    window = values[-length:]

    if np.isnan(window).all():
        return None

    return float(np.nanmin(window))


def _pine_previous_highest(
    values: Optional[np.ndarray],
    length: int
) -> Optional[float]:

    if values is None:
        return None

    if length <= 0:
        return None

    # Equivalent to ta.highest(h1, length)
    #
    # h1 is the previous-bar series, therefore the current
    # calculation uses the historical window ending one bar
    # before the current bar.

    if len(values) < length + 1:
        return None

    window = values[-(length + 1):-1]

    if np.isnan(window).all():
        return None

    return float(np.nanmax(window))


def _pine_previous_lowest(
    values: Optional[np.ndarray],
    length: int
) -> Optional[float]:

    if values is None:
        return None

    if length <= 0:
        return None

    # Equivalent to ta.lowest(l1, length)

    if len(values) < length + 1:
        return None

    window = values[-(length + 1):-1]

    if np.isnan(window).all():
        return None

    return float(np.nanmin(window))


def _historical_value(
    values: Optional[np.ndarray],
    bars_back: int
) -> Optional[float]:

    if values is None:
        return None

    if bars_back <= 0:
        return None

    if len(values) <= bars_back:
        return None

    value = values[-1 - bars_back]

    if np.isnan(value):
        return None

    return float(value)


# ======================================================
# MAIN LIQUIDITY UPDATE
# ======================================================

def update_market_liquidity(
    tf: str,
    bar_index: int,
    time: Optional[int],
    c: float,
    h: float,
    l: float,
    o: float,
    h1: Optional[float],
    l1: Optional[float],
    atr: Optional[float],

    # Historical OHLCV series
    highs: Optional[np.ndarray] = None,
    lows: Optional[np.ndarray] = None,
    volumes: Optional[np.ndarray] = None,

    # --------------------------------------------------
    # Absorption inputs
    #
    # These correspond directly to upstream Pine values:
    #
    # volumeMA
    # volumeRatio
    # candleRange
    # upperWick
    # lowerWick
    # wickRatio
    # supportHigh
    # resistanceLow
    #
    # They are passed in rather than recalculated here.
    # This keeps ownership of those calculations outside
    # Liquidity Detection.
    # --------------------------------------------------

    volume: Optional[float] = None,
    volume_ma: Optional[float] = None,
    volume_ratio: Optional[float] = None,
    candle_range: Optional[float] = None,
    upper_wick: Optional[float] = None,
    lower_wick: Optional[float] = None,
    wick_ratio: Optional[float] = None,
    support_high: Optional[float] = None,
    resistance_low: Optional[float] = None,

    # --------------------------------------------------
    # Original Pine constants
    # --------------------------------------------------

    liquidity_lookback: int = 50,
    external_liquidity_lookback: int = 200,
    internal_liquidity_lookback: int = 50,
    liquidity_cluster_tolerance: float = 0.002,

    is_confirmed: bool = True,
) -> MarketLiquidity:

    # --------------------------------------------------
    # Memory access
    # --------------------------------------------------

    memory = get_liquidity_memory(tf)

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    result = MarketLiquidity()

    # ==================================================
    # 4.2.16 LIQUIDITY DETECTION
    # ==================================================
    #
    # SweepDetected:
    #
    # - Liquidity event only
    # - Indicates liquidity was taken
    # - No confirmation
    # - Must NOT be used as trade confirmation
    #
    # SweepReclaim / SweepReject:
    #
    # - Confirmed reaction after liquidity event
    # - Valid for price action confirmation
    # - Can be consumed by scoring engines
    #
    # RULE:
    #
    # Location / Context:
    #     bullSweepDetected
    #     bearSweepDetected
    #
    # Confirmation:
    #     bullSweepReclaim
    #     bearSweepReject
    #
    # Never replace confirmation with detection.
    # ==================================================

    # ==================================================
    # INITIAL STATE
    # ==================================================

    # Pine:
    #
    # bool bidAbsorption = false
    # bool askAbsorption = false
    # float bidAbsorptionStrength = 0.0
    # float askAbsorptionStrength = 0.0
    # float nearestBuyLiquidityPriceDistance = na
    # float nearestBuyLiquidityATRDistance = na
    # float nearestSellLiquidityPriceDistance = na
    # float nearestSellLiquidityATRDistance = na
    #
    # These defaults are already represented by MarketLiquidity.

    # ==================================================
    # RECENT SWING LIQUIDITY
    # ==================================================

    recent_high_liquidity = _pine_highest(
        highs,
        liquidity_lookback
    )

    recent_low_liquidity = _pine_lowest(
        lows,
        liquidity_lookback
    )

    prev_low_liquidity = _pine_previous_lowest(
        lows,
        liquidity_lookback
    )

    prev_high_liquidity = _pine_previous_highest(
        highs,
        liquidity_lookback
    )

    result.liquidity_high = recent_high_liquidity
    result.liquidity_low = recent_low_liquidity

    result.prev_low_liquidity = prev_low_liquidity
    result.prev_high_liquidity = prev_high_liquidity

    # ==================================================
    # DISTANCE FROM CURRENT PRICE
    # ==================================================

    liquidity_high_distance = None
    liquidity_low_distance = None

    if recent_high_liquidity is not None and c != 0:
        liquidity_high_distance = (
            (recent_high_liquidity - c) / c
        ) * 100.0

    if recent_low_liquidity is not None and c != 0:
        liquidity_low_distance = (
            (c - recent_low_liquidity) / c
        ) * 100.0

    result.liquidity_high_distance = liquidity_high_distance
    result.liquidity_low_distance = liquidity_low_distance

    # ==================================================
    # EQUAL HIGHS / LOWS
    # ==================================================

    equal_high_liquidity = None
    equal_low_liquidity = None

    if h1 is not None and c != 0:
        equal_high_liquidity = (
            abs(h - h1) / c < 0.001
        )

    if l1 is not None and c != 0:
        equal_low_liquidity = (
            abs(l - l1) / c < 0.001
        )

    result.equal_high_liquidity = equal_high_liquidity
    result.equal_low_liquidity = equal_low_liquidity

    # ==================================================
    # LIQUIDITY SWEEP CONTEXT
    # ==================================================

    # Bullish sweep:
    # Takes sell-side liquidity and reclaims level.

    bull_sweep_detected = None

    if prev_low_liquidity is not None:
        bull_sweep_detected = l < prev_low_liquidity

    bull_sweep_reclaim = None

    if bull_sweep_detected is not None:
        # recentLowLiquidity[1] is equivalent to the
        # previous rolling low.
        if prev_low_liquidity is not None:
            bull_sweep_reclaim = (
                bull_sweep_detected
                and c > prev_low_liquidity
            )
        else:
            bull_sweep_reclaim = False

    # Bearish sweep:
    # Takes buy-side liquidity and rejects level.

    bear_sweep_detected = None

    if prev_high_liquidity is not None:
        bear_sweep_detected = h > prev_high_liquidity

    bear_sweep_reject = None

    if bear_sweep_detected is not None:
        # recentHighLiquidity[1] is equivalent to the
        # previous rolling high.
        if prev_high_liquidity is not None:
            bear_sweep_reject = (
                bear_sweep_detected
                and c < prev_high_liquidity
            )
        else:
            bear_sweep_reject = False

    result.bull_sweep_detected = bull_sweep_detected
    result.bear_sweep_detected = bear_sweep_detected

    result.bull_sweep_reclaim = bull_sweep_reclaim
    result.bear_sweep_reject = bear_sweep_reject

    # ==================================================
    # SWEEP STRENGTH
    # ==================================================

    bull_sweep_strength = None
    bear_sweep_strength = None

    if bull_sweep_detected is not None:

        if bull_sweep_detected:
            if (
                prev_low_liquidity is not None
                and atr is not None
                and atr != 0
            ):
                bull_sweep_strength = min(
                    abs(prev_low_liquidity - l) / atr,
                    5.0
                )
            else:
                bull_sweep_strength = None

        else:
            bull_sweep_strength = 0.0

    if bear_sweep_detected is not None:

        if bear_sweep_detected:
            if (
                prev_high_liquidity is not None
                and atr is not None
                and atr != 0
            ):
                bear_sweep_strength = min(
                    abs(h - prev_high_liquidity) / atr,
                    5.0
                )
            else:
                bear_sweep_strength = None

        else:
            bear_sweep_strength = 0.0

    result.bull_sweep_strength = bull_sweep_strength
    result.bear_sweep_strength = bear_sweep_strength

    # ==================================================
    # ABSORPTION
    # ==================================================

    elevated_volume = False
    support_interaction = False
    resistance_interaction = False
    bullish_rejection = False
    bearish_rejection = False

    # Pine:
    #
    # bool elevatedVolume =
    #     not na(volumeMA) and volume >= volumeMA * 1.5

    if volume_ma is not None and volume is not None:
        elevated_volume = volume >= volume_ma * 1.5

    # Pine:
    #
    # bool supportInteraction =
    #     not na(supportHigh)
    #     and l <= supportHigh
    #     and c >= supportHigh

    if support_high is not None:
        support_interaction = (
            l <= support_high
            and c >= support_high
        )

    # Pine:
    #
    # bool resistanceInteraction =
    #     not na(resistanceLow)
    #     and h >= resistanceLow
    #     and c <= resistanceLow

    if resistance_low is not None:
        resistance_interaction = (
            h >= resistance_low
            and c <= resistance_low
        )

    # Pine:
    #
    # bool bullishRejection =
    #     candleRange > 0
    #     and lowerWick / candleRange >= 0.35
    #     and c > o

    if candle_range is not None and lower_wick is not None:
        if candle_range > 0:
            bullish_rejection = (
                lower_wick / candle_range >= 0.35
                and c > o
            )

    # Pine:
    #
    # bool bearishRejection =
    #     candleRange > 0
    #     and upperWick / candleRange >= 0.35
    #     and c < o

    if candle_range is not None and upper_wick is not None:
        if candle_range > 0:
            bearish_rejection = (
                upper_wick / candle_range >= 0.35
                and c < o
            )

    # ==================================================
    # ABSORPTION FLAGS
    # ==================================================

    bid_absorption = (
        support_interaction
        and elevated_volume
        and bullish_rejection
    )

    ask_absorption = (
        resistance_interaction
        and elevated_volume
        and bearish_rejection
    )

    result.bid_absorption = bid_absorption
    result.ask_absorption = ask_absorption

    # ==================================================
    # ABSORPTION STRENGTH
    # ==================================================

    bid_absorption_strength = 0.0
    ask_absorption_strength = 0.0

    if bid_absorption:

        if volume_ratio is not None:
            bid_absorption_strength += min(
                volume_ratio * 20.0,
                30.0
            )

        if wick_ratio is not None:
            bid_absorption_strength += min(
                wick_ratio * 50.0,
                30.0
            )

        if bull_sweep_detected:
            bid_absorption_strength += 20.0

        if bull_sweep_reclaim:
            bid_absorption_strength += 20.0

        bid_absorption_strength = min(
            bid_absorption_strength,
            100.0
        )

    if ask_absorption:

        if volume_ratio is not None:
            ask_absorption_strength += min(
                volume_ratio * 20.0,
                30.0
            )

        if wick_ratio is not None:
            ask_absorption_strength += min(
                wick_ratio * 50.0,
                30.0
            )

        if bear_sweep_detected:
            ask_absorption_strength += 20.0

        if bear_sweep_reject:
            ask_absorption_strength += 20.0

        ask_absorption_strength = min(
            ask_absorption_strength,
            100.0
        )

    result.bid_absorption_strength = bid_absorption_strength
    result.ask_absorption_strength = ask_absorption_strength

    # ==================================================
    # LIQUIDITY TYPE
    # ==================================================

    # Pine:
    #
    # string liquidityType =
    #
    #     equalLowLiquidity and bullSweepDetected
    #         ? "SELL_SIDE_EQUAL_LOW" :
    #
    #     equalHighLiquidity and bearSweepDetected
    #         ? "BUY_SIDE_EQUAL_HIGH" :
    #
    #     bullSweepDetected
    #         ? "SELL_SIDE_SWEEP" :
    #
    #     bearSweepDetected
    #         ? "BUY_SIDE_SWEEP" :
    #
    #     "NONE"

    liquidity_type = "NONE"

    if (
        equal_low_liquidity
        and bull_sweep_detected
    ):
        liquidity_type = "SELL_SIDE_EQUAL_LOW"

    elif (
        equal_high_liquidity
        and bear_sweep_detected
    ):
        liquidity_type = "BUY_SIDE_EQUAL_HIGH"

    elif bull_sweep_detected:
        liquidity_type = "SELL_SIDE_SWEEP"

    elif bear_sweep_detected:
        liquidity_type = "BUY_SIDE_SWEEP"

    result.liquidity_type = liquidity_type

    # ==================================================
    # LIQUIDITY CONTEXT EXPANSION
    #
    # PURPOSE:
    #
    # Enhance liquidity identification.
    #
    # Detects:
    # - External liquidity pools
    # - Internal liquidity pools
    # - Liquidity clustering
    # - Liquidity age
    # - Liquidity importance
    # ==================================================

    # ==================================================
    # INPUTS
    # ==================================================

    # These are intentionally kept as local values because
    # they are constants from the Pine source.

    external_lookback = external_liquidity_lookback
    internal_lookback = internal_liquidity_lookback
    cluster_tolerance = liquidity_cluster_tolerance

    # ==================================================
    # EXTERNAL LIQUIDITY
    #
    # Major swing liquidity.
    # Used mainly by Swing Engine.
    #
    # Example:
    # Previous weekly/monthly extremes.
    # ==================================================

    external_high_liquidity = _pine_highest(
        highs,
        external_lookback
    )

    external_low_liquidity = _pine_lowest(
        lows,
        external_lookback
    )

    result.external_high_liquidity = external_high_liquidity
    result.external_low_liquidity = external_low_liquidity

    # ==================================================
    # EXTERNAL DISTANCE %
    # ==================================================

    external_high_distance_pct = None
    external_high_distance = None
    external_low_distance_pct = None
    external_low_distance = None

    if external_high_liquidity is not None and c != 0:

        external_high_distance_pct = (
            abs(external_high_liquidity - c) / c
        ) * 100.0

        external_high_distance = abs(
            external_high_liquidity - c
        )

    if external_low_liquidity is not None and c != 0:

        external_low_distance_pct = (
            abs(c - external_low_liquidity) / c
        ) * 100.0

        external_low_distance = abs(
            c - external_low_liquidity
        )

    result.external_high_distance_pct = (
        external_high_distance_pct
    )

    result.external_high_distance = (
        external_high_distance
    )

    result.external_low_distance_pct = (
        external_low_distance_pct
    )

    result.external_low_distance = (
        external_low_distance
    )

    # ==================================================
    # INTERNAL LIQUIDITY
    #
    # Short-term resting liquidity.
    # ==================================================

    internal_high_liquidity = _pine_highest(
        highs,
        internal_lookback
    )

    internal_low_liquidity = _pine_lowest(
        lows,
        internal_lookback
    )

    result.internal_high_liquidity = (
        internal_high_liquidity
    )

    result.internal_low_liquidity = (
        internal_low_liquidity
    )

    # ==================================================
    # INTERNAL DISTANCE
    # ==================================================

    internal_high_distance_pct = None
    internal_high_distance = None
    internal_low_distance_pct = None

    if internal_high_liquidity is not None and c != 0:

        internal_high_distance_pct = (
            abs(internal_high_liquidity - c) / c
        ) * 100.0

        internal_high_distance = abs(
            internal_high_liquidity - c
        )

    if internal_low_liquidity is not None and c != 0:

        internal_low_distance_pct = (
            abs(c - internal_low_liquidity) / c
        ) * 100.0

    result.internal_high_distance_pct = (
        internal_high_distance_pct
    )

    result.internal_high_distance = (
        internal_high_distance
    )

    result.internal_low_distance_pct = (
        internal_low_distance_pct
    )

    # ==================================================
    # LIQUIDITY CLUSTER DETECTION
    #
    # Multiple highs/lows around same area.
    #
    # Approximation of heatmap liquidity.
    # ==================================================

    high_cluster_count = 0
    low_cluster_count = 0

    # Pine:
    #
    # for i = 1 to 50
    #
    #     if math.abs(h[i] - externalHighLiquidity) / c
    #         <= liquidityClusterTolerance
    #
    #         highClusterCount += 1
    #
    #     if math.abs(l[i] - externalLowLiquidity) / c
    #         <= liquidityClusterTolerance
    #
    #         lowClusterCount += 1

    if (
        external_high_liquidity is not None
        and c != 0
        and highs is not None
    ):

        for i in range(1, 51):

            historical_high = _historical_value(
                highs,
                i
            )

            if historical_high is None:
                continue

            if (
                abs(
                    historical_high
                    - external_high_liquidity
                ) / c
                <= cluster_tolerance
            ):
                high_cluster_count += 1

    if (
        external_low_liquidity is not None
        and c != 0
        and lows is not None
    ):

        for i in range(1, 51):

            historical_low = _historical_value(
                lows,
                i
            )

            if historical_low is None:
                continue

            if (
                abs(
                    historical_low
                    - external_low_liquidity
                ) / c
                <= cluster_tolerance
            ):
                low_cluster_count += 1

    result.high_cluster_count = high_cluster_count
    result.low_cluster_count = low_cluster_count

    # ==================================================
    # CLUSTER SCORES
    # ==================================================

    high_liquidity_cluster_score = min(
        high_cluster_count / 3.0,
        5.0
    )

    low_liquidity_cluster_score = min(
        low_cluster_count / 3.0,
        5.0
    )

    high_liquidity_cluster = (
        high_liquidity_cluster_score >= 2.0
    )

    low_liquidity_cluster = (
        low_liquidity_cluster_score >= 2.0
    )

    result.high_liquidity_cluster_score = (
        high_liquidity_cluster_score
    )

    result.low_liquidity_cluster_score = (
        low_liquidity_cluster_score
    )

    result.high_liquidity_cluster = (
        high_liquidity_cluster
    )

    result.low_liquidity_cluster = (
        low_liquidity_cluster
    )

    # ==================================================
    # LIQUIDITY AGE
    #
    # Older liquidity generally has more importance.
    # ==================================================

    high_liquidity_age = None
    low_liquidity_age = None

    # Pine:
    #
    # for i = 1 to externalLiquidityLookback
    #
    #     if na(highLiquidityAge)
    #         and math.abs(
    #             h[i] - externalHighLiquidity
    #         ) / c < 0.0005
    #
    #         highLiquidityAge := i

    if (
        external_high_liquidity is not None
        and c != 0
        and highs is not None
    ):

        for i in range(1, external_lookback + 1):

            if high_liquidity_age is not None:
                break

            historical_high = _historical_value(
                highs,
                i
            )

            if historical_high is None:
                continue

            if (
                abs(
                    historical_high
                    - external_high_liquidity
                ) / c
                < 0.0005
            ):
                high_liquidity_age = i

    # Pine:
    #
    #     if na(lowLiquidityAge)
    #         and math.abs(
    #             l[i] - externalLowLiquidity
    #         ) / c < 0.0005
    #
    #         lowLiquidityAge := i

    if (
        external_low_liquidity is not None
        and c != 0
        and lows is not None
    ):

        for i in range(1, external_lookback + 1):

            if low_liquidity_age is not None:
                break

            historical_low = _historical_value(
                lows,
                i
            )

            if historical_low is None:
                continue

            if (
                abs(
                    historical_low
                    - external_low_liquidity
                ) / c
                < 0.0005
            ):
                low_liquidity_age = i

    result.high_liquidity_age = high_liquidity_age
    result.low_liquidity_age = low_liquidity_age

    # ==================================================
    # LIQUIDITY IMPORTANCE
    #
    # Generic market fact.
    #
    # Not bullish.
    # Not bearish.
    # ==================================================

    high_liquidity_importance = 0.0
    low_liquidity_importance = 0.0

    # ==================================================
    # DISTANCE FACTOR
    # ==================================================

    if external_high_distance_pct is not None:

        high_liquidity_importance += max(
            0.0,
            5.0 - external_high_distance_pct
        )

    if external_low_distance_pct is not None:

        low_liquidity_importance += max(
            0.0,
            5.0 - external_low_distance_pct
        )

    # Pine declares this but it is not subsequently used.
    # It is retained here as the source constant for
    # traceability.

    liquidity_max_distance_pct = 5.0

    # ==================================================
    # CLUSTER FACTOR
    # ==================================================

    liquidity_cluster_importance = 2.0

    if high_liquidity_cluster:
        high_liquidity_importance += (
            liquidity_cluster_importance
        )

    if low_liquidity_cluster:
        low_liquidity_importance += (
            liquidity_cluster_importance
        )

    # ==================================================
    # AGE FACTOR
    # ==================================================

    if high_liquidity_age is not None:

        high_liquidity_importance += min(
            high_liquidity_age / 50.0,
            3.0
        )

    if low_liquidity_age is not None:

        low_liquidity_importance += min(
            low_liquidity_age / 50.0,
            3.0
        )

    # ==================================================
    # CAP
    # ==================================================

    high_liquidity_importance = min(
        high_liquidity_importance,
        10.0
    )

    low_liquidity_importance = min(
        low_liquidity_importance,
        10.0
    )

    result.high_liquidity_importance = (
        high_liquidity_importance
    )

    result.low_liquidity_importance = (
        low_liquidity_importance
    )

    # ==================================================
    # LIQUIDITY LOCATION TYPE
    # ==================================================

    if (
        high_liquidity_cluster
        and low_liquidity_cluster
    ):
        liquidity_location = "BOTH_CLUSTER"

    elif high_liquidity_cluster:
        liquidity_location = "BUY_SIDE_CLUSTER"

    elif low_liquidity_cluster:
        liquidity_location = "SELL_SIDE_CLUSTER"

    else:
        liquidity_location = "NO_CLUSTER"

    result.liquidity_location = liquidity_location

    # ==================================================
    # LIQUIDITY SIDE
    # ==================================================

    if (
        external_low_liquidity is not None
        and c < external_low_liquidity
    ):
        liquidity_side = "SELL_SIDE_NEAR"

    elif (
        external_high_liquidity is not None
        and c > external_high_liquidity
    ):
        liquidity_side = "BUY_SIDE_NEAR"

    else:
        liquidity_side = "MID_RANGE"

    result.liquidity_side = liquidity_side

    # ==================================================
    # NEAREST LIQUIDITY
    # ==================================================

    nearest_buy_liquidity_pct = None
    nearest_sell_liquidity_pct = None

    nearest_buy_liquidity_price = None
    nearest_sell_liquidity_price = None

    nearest_buy_liquidity_price_distance = None
    nearest_sell_liquidity_price_distance = None

    nearest_buy_liquidity_atr_distance = None
    nearest_sell_liquidity_atr_distance = None

    # ==================================================
    # BUY SIDE
    # ==================================================

    if (
        internal_high_distance_pct is not None
        and external_high_distance_pct is not None
    ):

        nearest_buy_liquidity_pct = min(
            internal_high_distance_pct,
            external_high_distance_pct
        )

    elif internal_high_distance_pct is not None:

        nearest_buy_liquidity_pct = (
            internal_high_distance_pct
        )

    elif external_high_distance_pct is not None:

        nearest_buy_liquidity_pct = (
            external_high_distance_pct
        )

    if (
        nearest_buy_liquidity_pct is not None
        and atr is not None
        and c > 0
    ):

        nearest_buy_liquidity_price_distance = (
            c
            * nearest_buy_liquidity_pct
            / 100.0
        )

        nearest_buy_liquidity_price = (
            c
            + nearest_buy_liquidity_price_distance
        )

        if atr != 0:

            nearest_buy_liquidity_atr_distance = (
                nearest_buy_liquidity_price_distance
                / atr
            )

    # ==================================================
    # SELL SIDE
    # ==================================================
    #
    # IMPORTANT:
    #
    # Original Pine source contains:
    #
    #     if not na(internalLowDistance)
    #
    # but the defined variable is:
    #
    #     internalLowDistancePct
    #
    # Therefore the compilable faithful translation uses
    # internal_low_distance_pct here.
    #
    # No new calculation is introduced.
    # ==================================================

    if (
        internal_low_distance_pct is not None
        and external_low_distance_pct is not None
    ):

        nearest_sell_liquidity_pct = min(
            internal_low_distance_pct,
            external_low_distance_pct
        )

    elif internal_low_distance_pct is not None:

        nearest_sell_liquidity_pct = (
            internal_low_distance_pct
        )

    elif external_low_distance_pct is not None:

        nearest_sell_liquidity_pct = (
            external_low_distance_pct
        )

    if (
        nearest_sell_liquidity_pct is not None
        and atr is not None
        and c > 0
    ):

        nearest_sell_liquidity_price_distance = (
            c
            * nearest_sell_liquidity_pct
            / 100.0
        )

        nearest_sell_liquidity_price = (
            c
            - nearest_sell_liquidity_price_distance
        )

        if atr != 0:

            nearest_sell_liquidity_atr_distance = (
                nearest_sell_liquidity_price_distance
                / atr
            )

    # ==================================================
    # FINAL OUTPUT ASSIGNMENT
    # ==================================================

    result.nearest_buy_liquidity_pct = (
        nearest_buy_liquidity_pct
    )

    result.nearest_sell_liquidity_pct = (
        nearest_sell_liquidity_pct
    )

    result.nearest_buy_liquidity_price = (
        nearest_buy_liquidity_price
    )

    result.nearest_sell_liquidity_price = (
        nearest_sell_liquidity_price
    )

    result.nearest_buy_liquidity_price_distance = (
        nearest_buy_liquidity_price_distance
    )

    result.nearest_sell_liquidity_price_distance = (
        nearest_sell_liquidity_price_distance
    )

    result.nearest_buy_liquidity_atr_distance = (
        nearest_buy_liquidity_atr_distance
    )

    result.nearest_sell_liquidity_atr_distance = (
        nearest_sell_liquidity_atr_distance
    )

    # ==================================================
    # RETURN
    # ==================================================

    return result