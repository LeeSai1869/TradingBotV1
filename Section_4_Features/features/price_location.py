from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class PriceLocationFeatures:
    price_above_ema50: bool = False
    price_below_ema50: bool = False
    price_above_ema200: bool = False
    price_below_ema200: bool = False
    price_above_ema300: bool = False
    price_below_ema300: bool = False

def compute(df, context):
    if df is None or df.empty: return PriceLocationFeatures()
    c=float(df["close"].iloc[-1])
    e7=context["ema7"]; pe7=context["prev_ema7"]
    e25=context["ema25"]; pe25=context["prev_ema25"]
    e50=context["ema50"]; pe50=context["prev_ema50"]
    e100=context["ema100"]; pe100=context["prev_ema100"]
    e200=context["ema200"]; pe200=context["prev_ema200"]
    e300=context["ema300"]; pe300=context["prev_ema300"]
    return PriceLocationFeatures(
        price_above_ema50=c > e50,
        price_below_ema50=c < e50,
        price_above_ema200=c > e200,
        price_below_ema200=c < e200,
        price_above_ema300=c > e300,
        price_below_ema300=c < e300,
    )

NAME="price_location"
INPUTS=("df","context")
OUTPUT_FIELDS=('price_above_ema50', 'price_below_ema50', 'price_above_ema200', 'price_below_ema200', 'price_above_ema300', 'price_below_ema300')
