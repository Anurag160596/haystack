"""
Market data from Nasdaq's public website API (api.nasdaq.com). No key needed.

Used to read the Nasdaq market before ranking: index levels for the Nasdaq Composite and Nasdaq-100, market
status, how many Nasdaq-100 stocks rose or fell, the biggest Nasdaq-100 movers, and the most-traded stocks by
dollar volume.
"""

import json
import urllib.request
from typing import Any

NASDAQ_API = "https://api.nasdaq.com/api"
INDICES = {"COMP": "Nasdaq Composite", "NDX": "Nasdaq-100"}


def _get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{NASDAQ_API}/{path}", headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not payload.get("data"):
        raise ValueError(f"Nasdaq returned no data for {path}: {payload.get('status')}")
    return payload["data"]


def _primary(data: dict[str, Any]) -> dict[str, Any]:
    p = data.get("primaryData") or {}
    return {
        "last": p.get("lastSalePrice"),
        "change": p.get("netChange"),
        "percent_change": p.get("percentageChange"),
        "as_of": p.get("lastTradeTimestamp"),
    }


def _mover(row: dict[str, Any]) -> dict[str, Any]:
    try:
        percent = float(str(row.get("change", "")).rstrip("%").replace(",", ""))
    except ValueError:
        percent = None
    return {"symbol": row.get("symbol"), "name": row.get("name"), "last": row.get("lastSalePrice"), "percent": percent}


def market_overview(movers_per_table: int = 5) -> dict[str, Any]:
    """
    Return Nasdaq index levels, market status, Nasdaq-100 breadth and biggest movers, and the most-traded stocks.

    Nasdaq's exchange-wide "most advanced/declined" lists are skipped: penny stocks and warrants dominate them.
    """
    overview: dict[str, Any] = {"indices": {}, "movers": {}}
    for symbol, name in INDICES.items():
        try:
            overview["indices"][name] = _primary(_get(f"quote/{symbol}/info?assetclass=index"))
        except Exception as e:
            overview["indices"][name] = {"error": str(e)}
    try:
        status = _get("market-info")
        overview["market_status"] = status.get("marketIndicator")
        overview["next_open"] = status.get("marketOpeningTime")
    except Exception as e:
        overview["market_status"] = f"unavailable: {e}"
    try:
        tables = _get("marketmovers?assetclass=stocks&limit=100")["STOCKS"]
        nasdaq_100 = [_mover(r) for r in tables.get("Nasdaq100Movers", {}).get("table", {}).get("rows", [])]
        nasdaq_100 = sorted((m for m in nasdaq_100 if m["percent"] is not None), key=lambda m: m["percent"])
        overview["nasdaq_100_breadth"] = {
            "advancing": sum(m["percent"] > 0 for m in nasdaq_100),
            "declining": sum(m["percent"] < 0 for m in nasdaq_100),
        }
        overview["movers"]["nasdaq_100_top_gainers"] = nasdaq_100[::-1][:movers_per_table]
        overview["movers"]["nasdaq_100_top_losers"] = nasdaq_100[:movers_per_table]
        overview["movers"]["most_traded_by_dollar_volume"] = [
            _mover(r)
            for r in tables.get("MostActiveByDollarVolume", {}).get("table", {}).get("rows", [])[:movers_per_table]
        ]
    except Exception as e:
        overview["movers"] = {"error": str(e)}
    return overview


def stock_summary(ticker: str) -> dict[str, Any]:
    """Return Nasdaq's quote and summary for one stock: price move, exchange, Nasdaq-100 membership, 1-year target."""
    symbol = ticker.upper().replace("-", ".")
    info = _get(f"quote/{symbol}/info?assetclass=stocks")
    summary = _get(f"quote/{symbol}/summary?assetclass=stocks").get("summaryData") or {}
    return {
        "ticker": ticker.upper(),
        "name": info.get("companyName"),
        "exchange": info.get("exchange"),
        "is_nasdaq_100": info.get("isNasdaq100"),
        **_primary(info),
        **{
            (field.get("label") or key): field.get("value") for key, field in summary.items() if isinstance(field, dict)
        },
    }
