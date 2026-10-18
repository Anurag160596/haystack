"""
Due-diligence checks that sit alongside the numeric scoring in `stock_agent.py`.

- Governance and legal screen: SEC filings (restatements, late filings, auditor changes, delisting and bankruptcy
  notices), ISS governance risk scores, and recent legal/regulatory headlines. A red flag is disqualifying.
- PESTLE scan: recent Political, Economic, Social, Technological, Legal and Environmental headlines for an industry.
- Sector moves: how each US sector ETF has performed against the S&P 500.

All sources are free. SEC EDGAR requires a User-Agent with a contact email; set `SEC_USER_AGENT`, e.g.
"Your Name you@example.com". Without it, the SEC part of the governance screen reports "unverified".
"""

import contextlib
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from functools import cache
from typing import Any

import yfinance as yf

GREEN, AMBER, RED, UNVERIFIED = "green", "amber", "red", "unverified"

# 8-K items that matter for governance. Red items disqualify a stock; amber items must be explained.
RED_8K_ITEMS = {
    "1.03": "Bankruptcy or receivership",
    "4.02": "Prior financial statements can no longer be relied on (restatement)",
}
AMBER_8K_ITEMS = {
    "4.01": "Change of auditor",
    # Item 3.01 covers both delisting notices and voluntary transfers between exchanges, so it needs reading.
    "3.01": "Delisting notice or transfer of listing; check which",
}
# A late-filing notice means the company could not file its annual or quarterly report on time.
RED_FORMS = {"NT 10-K": "Late annual report", "NT 10-Q": "Late quarterly report"}
LOOKBACK_DAYS = 730

LEGAL_QUERY = (
    "lawsuit OR investigation OR probe OR SEC OR DOJ OR FTC OR antitrust OR fraud OR settlement OR "
    '"class action" OR indictment OR subpoena OR fine OR penalty OR whistleblower'
)
# Headlines containing these words point at misconduct rather than routine litigation, so they escalate to amber.
SEVERE_TERMS = (
    "fraud", "indict", "criminal", "charged", "sec charges", "accounting", "restate", "whistleblower",
    "bribery", "embezzle", "money laundering", "insider trading", "misled investors", "subpoena",
)  # fmt: skip

PESTLE_QUERIES = {
    "political": "tariffs OR sanctions OR government OR election OR trade policy OR subsidies",
    "economic": "demand OR interest rates OR inflation OR pricing OR recession OR spending",
    "social": "consumers OR demographics OR labor OR workforce OR public opinion OR boycott",
    "technological": "AI OR innovation OR disruption OR new technology OR automation OR patent",
    "legal": "regulation OR antitrust OR lawsuit OR compliance OR ruling OR legislation",
    "environmental": "climate OR emissions OR sustainability OR ESG OR energy transition OR weather",
}

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
BENCHMARK = "SPY"


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def search_news(query: str, days: int = 30, limit: int = 8) -> list[dict[str, str]]:
    """Search Google News (RSS, no key needed) for recent US English headlines."""
    params = urllib.parse.urlencode({"q": f"{query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(_get(f"https://news.google.com/rss/search?{params}"))
    headlines = []
    for item in root.iter("item"):
        published = item.findtext("pubDate")
        with contextlib.suppress(TypeError, ValueError):
            published = parsedate_to_datetime(published).date().isoformat() if published else None
        headlines.append(
            {
                "title": item.findtext("title") or "",
                "source": item.findtext("source") or "",
                "published": published or "",
                "link": item.findtext("link") or "",
            }
        )
        if len(headlines) >= limit:
            break
    return headlines


# ---------------------------------------------------------------- governance and legal


def _sec_headers() -> dict[str, str] | None:
    user_agent = os.environ.get("SEC_USER_AGENT")
    return {"User-Agent": user_agent} if user_agent else None


@cache
def _sec_ciks() -> dict[str, int]:
    data = json.loads(_get("https://www.sec.gov/files/company_tickers.json", _sec_headers()))
    return {row["ticker"].upper(): row["cik_str"] for row in data.values()}


def sec_filing_flags(ticker: str, today: date | None = None) -> dict[str, Any]:
    """Look for red and amber governance events in a company's SEC filings over the last two years."""
    if _sec_headers() is None:
        return {"status": UNVERIFIED, "reason": "SEC_USER_AGENT is not set, so SEC filings were not checked"}
    cik = _sec_ciks().get(ticker.upper()) or _sec_ciks().get(ticker.upper().replace("-", "."))
    if cik is None:
        return {"status": UNVERIFIED, "reason": f"No SEC registrant found for {ticker}"}

    submissions = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", _sec_headers()))
    return classify_filings(submissions["filings"]["recent"], today or date.today())


def classify_filings(recent: dict[str, list], today: date) -> dict[str, Any]:
    """Classify the `filings.recent` block of an EDGAR submissions response."""
    cutoff = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    red, amber = [], []
    for form, filed, items in zip(recent["form"], recent["filingDate"], recent["items"], strict=True):
        if filed < cutoff:
            continue
        if form in RED_FORMS:
            red.append(f"{filed}: {form} ({RED_FORMS[form]})")
        if form.startswith("8-K"):
            for item in (i.strip() for i in items.split(",") if i.strip()):
                if item in RED_8K_ITEMS:
                    red.append(f"{filed}: 8-K item {item} ({RED_8K_ITEMS[item]})")
                elif item in AMBER_8K_ITEMS:
                    amber.append(f"{filed}: 8-K item {item} ({AMBER_8K_ITEMS[item]})")
    status = RED if red else AMBER if amber else GREEN
    return {"status": status, "red_flags": red, "amber_flags": amber, "lookback_days": LOOKBACK_DAYS}


def iss_governance_flags(info: dict[str, Any]) -> dict[str, Any]:
    """Read ISS governance risk scores (1 = low risk, 10 = high risk) from yfinance info."""
    scores = {
        key: info.get(key)
        for key in ("overallRisk", "auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk")
    }
    if all(v is None for v in scores.values()):
        return {"status": UNVERIFIED, "reason": "No ISS governance scores available", "scores": scores}
    # Scores are deciles against peers, so high sub-scores are common; only a high overall score is a flag.
    overall = scores["overallRisk"]
    amber = [f"ISS overall governance risk is {overall}/10"] if isinstance(overall, int) and overall >= 8 else []
    notes = [
        f"ISS {key} is {value}/10"
        for key, value in scores.items()
        if key != "overallRisk" and isinstance(value, int) and value >= 9
    ]
    return {"status": AMBER if amber else GREEN, "amber_flags": amber, "notes": notes, "scores": scores}


def legal_news_flags(company: str, days: int = 90) -> dict[str, Any]:
    """Find recent legal and regulatory headlines; misconduct-type headlines escalate to amber."""
    headlines = search_news(f'"{company}" ({LEGAL_QUERY})', days=days, limit=10)
    severe = [h for h in headlines if any(term in h["title"].lower() for term in SEVERE_TERMS)]
    return {
        "status": AMBER if severe else GREEN,
        "severe_headlines": severe,
        "other_legal_headlines": [h for h in headlines if h not in severe],
        "lookback_days": days,
    }


def combine_status(*statuses: str) -> str:
    """Red beats amber beats unverified beats green."""
    for status in (RED, AMBER, UNVERIFIED):
        if status in statuses:
            return status
    return GREEN


def governance_screen(ticker: str, info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fast screen from SEC filings and ISS scores only, used to filter rankings."""
    info = info if info is not None else (yf.Ticker(ticker).info or {})
    try:
        sec = sec_filing_flags(ticker)
    except Exception as e:
        sec = {"status": UNVERIFIED, "reason": f"SEC lookup failed: {e}"}
    iss = iss_governance_flags(info)
    return {"ticker": ticker.upper(), "status": combine_status(sec["status"], iss["status"]), "sec": sec, "iss": iss}


def governance_check(ticker: str) -> dict[str, Any]:
    """Full governance and legal check: SEC filings, ISS scores, and recent legal headlines."""
    info = yf.Ticker(ticker).info or {}
    result = governance_screen(ticker, info)
    company = info.get("shortName") or info.get("longName") or ticker
    try:
        news = legal_news_flags(company)
    except Exception as e:
        news = {"status": UNVERIFIED, "reason": f"News search failed: {e}"}
    result["legal_news"] = news
    result["status"] = combine_status(result["status"], news["status"])
    result["rule"] = {
        RED: "Disqualified. Do not recommend this stock.",
        AMBER: "Every amber flag must be explained to the user before any recommendation.",
        UNVERIFIED: "Some checks could not run. Say which, and do not call the company clean.",
        GREEN: "No governance or legal red flags found in the sources checked.",
    }[result["status"]]
    return result


# ---------------------------------------------------------------- industry context


def pestle_scan(topic: str, days: int = 30, per_dimension: int = 4) -> dict[str, Any]:
    """Collect recent headlines about an industry or company for each PESTLE dimension."""
    scan: dict[str, Any] = {"topic": topic, "lookback_days": days}
    for dimension, keywords in PESTLE_QUERIES.items():
        try:
            scan[dimension] = search_news(f"{topic} ({keywords})", days=days, limit=per_dimension)
        except Exception as e:
            scan[dimension] = [{"error": str(e)}]
    return scan


def _trailing_returns(closes: list[float]) -> dict[str, float | None]:
    def back(days: int) -> float | None:
        return closes[-1] / closes[-1 - days] - 1 if len(closes) > days else None

    return {
        "return_1m": back(21),
        "return_3m": back(63),
        "return_6m": back(126),
        "return_1y": closes[-1] / closes[0] - 1 if len(closes) > 1 else None,
    }


@cache
def sector_moves() -> dict[str, Any]:
    """Return each sector ETF's trailing returns and how far it is ahead of or behind the S&P 500."""
    tickers = [BENCHMARK, *SECTOR_ETFS.values()]
    closes = yf.download(tickers, period="1y", auto_adjust=True, progress=False)["Close"]
    returns = {t: _trailing_returns([float(c) for c in closes[t].dropna()]) for t in tickers}
    benchmark = returns[BENCHMARK]

    sectors = {}
    for sector, etf in SECTOR_ETFS.items():
        r = returns[etf]
        relative = {
            f"vs_sp500_{k.removeprefix('return_')}": (r[k] - benchmark[k])
            if r[k] is not None and benchmark[k] is not None
            else None
            for k in r
        }
        sectors[sector] = {"etf": etf, **r, **relative}
    return {"benchmark": {"ticker": BENCHMARK, **benchmark}, "sectors": sectors}
