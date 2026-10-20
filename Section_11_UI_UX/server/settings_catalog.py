"""Read-only settings view of the existing registry; never changes policy."""
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "Section_1_Global_Core" / "Symbols" / "symbols.json"


def _ineligible(row):
    reason = row.get("reason", "")
    return reason in {"auto:meme", "auto:stablecoin", "not_on_binance"}


def read_coin_catalog():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    top = {row["symbol"] for row in data.get("top50", [])}
    approved = data.get("approved", [])
    disapproved = data.get("disapproved", [])
    # Preserve Core's distinction: falling out of top50 means inactive,
    # while eligibility failures are grouped separately for presentation.
    return {
        "approved": [row for row in approved if row["symbol"] in top],
        "inactive": [row for row in approved if row["symbol"] not in top],
        "disapproved": [row for row in disapproved if not _ineligible(row)],
        "ineligible": [row for row in disapproved if _ineligible(row)],
        "pending": data.get("pending", []),
        "staged": data.get("staged", []),
    }
