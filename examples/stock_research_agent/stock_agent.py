"""
A Haystack Agent that researches US stocks and explains which one looks "best" for a given investor profile.

There is no single best stock: the answer depends on what you want (growth, value, income, low risk) and
how long you plan to hold. The agent pulls live market data with yfinance, scores candidates on several
factors, weights those factors by your profile, and explains its reasoning and the risks.

Before recommending anything it also checks:
- governance and legal: SEC filings, ISS governance scores, and legal headlines. A red flag disqualifies a stock.
- industry tailwinds and headwinds: sector performance against the S&P 500 and a PESTLE news scan.

This is an educational research tool, not financial advice.

Usage:
    export OPENAI_API_KEY=...
    export SEC_USER_AGENT="Your Name you@example.com"   # required by SEC EDGAR for the filings check
    python stock_agent.py                         # interactive chat
    python stock_agent.py "Best growth stock among NVDA, MSFT, AMZN?"
"""

import math
import statistics
import sys
from typing import Annotated, Any, Literal

import yfinance as yf
from due_diligence import RED, governance_check, governance_screen, pestle_scan, sector_moves

from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.generators.utils import print_streaming_chunk
from haystack.dataclasses import ChatMessage, ChatRole
from haystack.tools import tool

# A liquid, sector-diverse slice of large US companies used when the user does not name candidates.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM",
    "V", "MA", "LLY", "UNH", "JNJ", "ABBV", "MRK", "XOM", "CVX", "PG",
    "KO", "PEP", "COST", "WMT", "HD", "ORCL", "CRM", "ADBE", "AMD", "NFLX",
]  # fmt: skip

Profile = Literal["balanced", "growth", "value", "income", "low_risk"]

# How much each factor counts for each profile. Weights per profile sum to 1.
PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {"growth": 0.2, "profitability": 0.2, "valuation": 0.2, "momentum": 0.2, "safety": 0.2},
    "growth": {"growth": 0.4, "profitability": 0.15, "valuation": 0.05, "momentum": 0.3, "safety": 0.1},
    "value": {"growth": 0.1, "profitability": 0.25, "valuation": 0.45, "momentum": 0.05, "safety": 0.15},
    "income": {"growth": 0.05, "profitability": 0.2, "valuation": 0.2, "momentum": 0.05, "safety": 0.2, "yield": 0.3},
    "low_risk": {"growth": 0.05, "profitability": 0.25, "valuation": 0.15, "momentum": 0.05, "safety": 0.5},
}

# Raw metrics feeding each factor, and whether higher is better.
FACTOR_METRICS: dict[str, list[tuple[str, bool]]] = {
    "growth": [("revenue_growth", True), ("earnings_growth", True)],
    "profitability": [("profit_margin", True), ("return_on_equity", True)],
    "valuation": [
        ("forward_pe", False),
        ("peg_ratio", False),
        ("price_to_book", False),
        ("ev_to_ebitda", False),
        ("fcf_yield", True),
    ],
    # sector_vs_sp500_6m is the industry tailwind: how the stock's sector has done against the market
    "momentum": [("return_1y", True), ("return_6m", True), ("sector_vs_sp500_6m", True)],
    "safety": [("volatility", False), ("max_drawdown", True), ("debt_to_equity", False)],
    "yield": [("dividend_yield", True)],
}


# Valuation ratios where a negative value means losses or negative equity, which is worse than any positive value.
RATIOS_WORST_WHEN_NEGATIVE = {"forward_pe", "peg_ratio", "price_to_book", "ev_to_ebitda"}


def _num(value: Any) -> float | None:
    """Return value as a finite float, or None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _price_stats(closes: list[float]) -> dict[str, float | None]:
    """Compute trailing returns, annualized volatility, and max drawdown from daily closes (oldest first)."""
    if len(closes) < 2:
        return {"return_1y": None, "return_6m": None, "volatility": None, "max_drawdown": None}

    def trailing(days: int) -> float | None:
        if len(closes) <= days:
            return None
        return closes[-1] / closes[-1 - days] - 1

    daily = [b / a - 1 for a, b in zip(closes[:-1], closes[1:], strict=True) if a]
    volatility = statistics.stdev(daily) * math.sqrt(252) if len(daily) > 1 else None

    peak, max_drawdown = closes[0], 0.0
    for price in closes:
        peak = max(peak, price)
        max_drawdown = min(max_drawdown, price / peak - 1)

    return {
        "return_1y": closes[-1] / closes[0] - 1,
        "return_6m": trailing(126),
        "volatility": volatility,
        "max_drawdown": max_drawdown,  # negative number, closer to 0 is better
    }


def fetch_metrics(ticker: str) -> dict[str, Any]:
    """Fetch fundamentals and one year of price history for a ticker."""
    t = yf.Ticker(ticker.upper())
    info = t.info or {}
    closes = [float(c) for c in t.history(period="1y")["Close"].dropna()]
    if not closes and not info.get("longName"):
        raise ValueError(f"No data found for ticker '{ticker}'")

    # trailingAnnualDividendYield is a fraction; dividendYield is reported in percent by recent yfinance versions
    dividend_yield = _num(info.get("trailingAnnualDividendYield"))
    if dividend_yield is None and _num(info.get("dividendYield")) is not None:
        dividend_yield = _num(info.get("dividendYield")) / 100

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "price": _num(info.get("currentPrice")) or (closes[-1] if closes else None),
        "market_cap_billions": round(_num(info.get("marketCap")) / 1e9, 1) if _num(info.get("marketCap")) else None,
        "trailing_pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")),
        "peg_ratio": _num(info.get("trailingPegRatio") or info.get("pegRatio")),
        "price_to_book": _num(info.get("priceToBook")),
        "ev_to_ebitda": _num(info.get("enterpriseToEbitda")),
        "fcf_yield": _num(info.get("freeCashflow")) / _num(info.get("marketCap"))
        if _num(info.get("freeCashflow")) is not None and _num(info.get("marketCap"))
        else None,
        "revenue_growth": _num(info.get("revenueGrowth")),
        "earnings_growth": _num(info.get("earningsGrowth")),
        "profit_margin": _num(info.get("profitMargins")),
        "return_on_equity": _num(info.get("returnOnEquity")),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "dividend_yield": dividend_yield or 0.0,
        "beta": _num(info.get("beta")),
        "analyst_target_price": _num(info.get("targetMeanPrice")),
        "analyst_recommendation": info.get("recommendationKey"),
        # ISS governance risk scores, 1 (low risk) to 10 (high risk)
        **{
            k: info.get(k)
            for k in ("overallRisk", "auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk")
        },
        **_price_stats(closes),
    }


def score_candidates(metrics: list[dict[str, Any]], profile: str = "balanced") -> list[dict[str, Any]]:
    """
    Rank candidates against each other.

    Each metric is converted to a percentile rank (0-100) within the candidate set, metrics are averaged into
    factor scores, and factor scores are combined with the profile's weights. Missing metrics are skipped
    rather than penalized. Negative P/E-style ratios (loss-making companies) count as the worst valuation.
    """
    weights = PROFILE_WEIGHTS[profile]

    def percentile(metric: str, higher_is_better: bool) -> dict[str, float]:
        values = {}
        for m in metrics:
            v = _num(m.get(metric))
            if v is None:
                continue
            if not higher_is_better and metric in RATIOS_WORST_WHEN_NEGATIVE and v <= 0:
                v = math.inf
            values[m["ticker"]] = v if higher_is_better else -v
        if len(values) < 2:
            return dict.fromkeys(values, 50.0)
        ordered = sorted(values.values())
        return {k: 100 * ordered.index(v) / (len(ordered) - 1) for k, v in values.items()}

    metric_ranks = {
        (factor, metric): percentile(metric, hib) for factor, items in FACTOR_METRICS.items() for metric, hib in items
    }

    results = []
    for m in metrics:
        factor_scores = {}
        for factor, items in FACTOR_METRICS.items():
            ranks = [metric_ranks[(factor, metric)].get(m["ticker"]) for metric, _ in items]
            ranks = [r for r in ranks if r is not None]
            factor_scores[factor] = round(sum(ranks) / len(ranks), 1) if ranks else None

        used = {f: w for f, w in weights.items() if factor_scores.get(f) is not None}
        total = sum(factor_scores[f] * w for f, w in used.items()) / sum(used.values()) if used else 0.0
        results.append(
            {"ticker": m["ticker"], "name": m.get("name"), "score": round(total, 1), "factor_scores": factor_scores}
        )
    return sorted(results, key=lambda r: r["score"], reverse=True)


# ---------------------------------------------------------------- tools exposed to the agent


@tool
def get_stock_snapshot(ticker: Annotated[str, "US stock ticker symbol, e.g. 'AAPL'"]) -> dict[str, Any]:
    """
    Get a fundamentals and price snapshot for one US stock.

    Includes valuation (P/E, PEG, P/B), growth, margins, debt, dividend yield, 1y/6m returns, volatility,
    max drawdown, and analyst consensus.
    """
    try:
        return fetch_metrics(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


@tool
def rank_stocks(
    tickers: Annotated[
        list[str] | None, "Tickers to compare. Leave empty to screen a default large-cap universe."
    ] = None,
    profile: Annotated[Profile, "Investor profile that decides how factors are weighted"] = "balanced",
    top_n: Annotated[int, "How many top results to return"] = 10,
) -> dict[str, Any]:
    """
    Rank US stocks for an investor profile.

    Each stock gets 0-100 factor scores (growth, profitability, valuation, momentum including its sector's trend,
    safety, yield) relative to the other candidates, combined into an overall score. Scores are relative to the
    candidate set, not absolute. Stocks with a red governance flag in SEC filings are excluded from the ranking.
    """
    universe = [t.upper() for t in tickers] if tickers else DEFAULT_UNIVERSE
    metrics, errors = [], []
    for ticker in universe:
        try:
            metrics.append(fetch_metrics(ticker))
        except Exception as e:
            errors.append(f"{ticker}: {e}")

    try:
        sectors = sector_moves()["sectors"]
    except Exception as e:
        sectors = {}
        errors.append(f"sector moves: {e}")
    for m in metrics:
        m["sector_vs_sp500_6m"] = sectors.get(m.get("sector") or "", {}).get("vs_sp500_6m")

    screens = {m["ticker"]: governance_screen(m["ticker"], info=m) for m in metrics}
    excluded = [
        {"ticker": t, "red_flags": s["sec"].get("red_flags", [])} for t, s in screens.items() if s["status"] == RED
    ]
    eligible = [m for m in metrics if screens[m["ticker"]]["status"] != RED]

    ranked = score_candidates(eligible, profile)[:top_n]
    by_ticker = {m["ticker"]: m for m in metrics}
    for r in ranked:
        m = by_ticker[r["ticker"]]
        r["key_metrics"] = {
            k: m[k]
            for k in (
                "sector",
                "price",
                "forward_pe",
                "fcf_yield",
                "revenue_growth",
                "return_1y",
                "sector_vs_sp500_6m",
                "volatility",
                "dividend_yield",
            )
        }
        r["governance_screen"] = screens[r["ticker"]]["status"]
    return {
        "profile": profile,
        "weights": PROFILE_WEIGHTS[profile],
        "ranking": ranked,
        "excluded_for_governance": excluded,
        "note": "governance_screen covers SEC filings and ISS scores only; run check_governance_and_legal "
        "(which adds legal news) on any stock before recommending it",
        "errors": errors,
    }


@tool
def get_recent_news(
    ticker: Annotated[str, "US stock ticker symbol"], limit: Annotated[int, "Number of headlines"] = 5
) -> list[dict[str, Any]]:
    """Get recent news headlines for a stock, to spot catalysts or risks the numbers don't show."""
    try:
        items = yf.Ticker(ticker.upper()).news or []
    except Exception as e:
        return [{"error": str(e)}]
    headlines = []
    for item in items[:limit]:
        content = item.get("content", item)  # newer yfinance nests fields under "content"
        provider = content.get("provider")
        headlines.append(
            {
                "title": content.get("title"),
                "publisher": provider.get("displayName") if isinstance(provider, dict) else content.get("publisher"),
                "published": content.get("pubDate") or content.get("providerPublishTime"),
                "summary": content.get("summary"),
            }
        )
    return headlines


@tool
def check_governance_and_legal(ticker: Annotated[str, "US stock ticker symbol"]) -> dict[str, Any]:
    """
    Run the full governance and legal check on one stock. Required before recommending any stock.

    Checks the last two years of SEC filings (restatements, late filings, auditor changes, delisting and
    bankruptcy notices), ISS governance risk scores, and legal/regulatory headlines from the last 90 days.
    Returns status green, amber, red (disqualified) or unverified, with the evidence.
    """
    try:
        return governance_check(ticker)
    except Exception as e:
        return {"ticker": ticker, "status": "unverified", "error": str(e)}


@tool
def get_pestle_analysis(
    topic: Annotated[str, "Industry or company to scan, e.g. 'semiconductor industry' or 'Nvidia'"],
    days: Annotated[int, "How many days of news to look back"] = 30,
) -> dict[str, Any]:
    """
    Get recent PESTLE headlines for an industry or company, to judge its tailwinds and headwinds.

    Covers the political, economic, social, technological, legal and environmental dimensions.
    """
    return pestle_scan(topic, days=days)


@tool
def get_sector_moves() -> dict[str, Any]:
    """
    Get how each US sector has moved against the S&P 500, to see which industries lead or lag.

    Returns 1-month, 3-month, 6-month and 1-year returns of each sector ETF and SPY, and each sector's lead or lag.
    """
    try:
        return sector_moves()
    except Exception as e:
        return {"error": str(e)}


SYSTEM_PROMPT = """You are a careful equity research assistant for the US stock market.

Your job is to help the user understand which stock looks best *for them*, and why.

How to work:
1. "Best" depends on goals. If the user hasn't said, briefly ask (or assume "balanced" and say so):
   growth, value, income, or low risk; and their time horizon.
2. Use `get_sector_moves` to see which industries are leading or lagging the market.
3. Use `rank_stocks` to compare candidates (the user's tickers, or the default large-cap screen).
4. For the top 2-3, use `get_stock_snapshot`, `get_recent_news`, `check_governance_and_legal`, and
   `get_pestle_analysis` on the stock's industry.
5. Give a clear answer: your top pick for the stated profile, the runners-up, and why, citing the numbers.
6. For each pick, give:
   - Governance & legal: the status and every flag found, in plain language.
   - Industry tailwinds and headwinds: the sector's trend against the market, and a short PESTLE summary that
     labels each relevant point as a tailwind or headwind. Only cite headlines the tools returned.
   - Risks and what would make the pick wrong (valuation, concentration, drawdowns, news).
7. Explain jargon in plain language. Scores are relative to the candidate set; say so.

Governance rules (non-negotiable):
- Never recommend a stock you have not run `check_governance_and_legal` on.
- A "red" status disqualifies the stock, however well it scores. Say it was excluded and why.
- An "amber" stock can only be recommended if you explain every amber flag and why you judge it acceptable.
  Ongoing fraud, accounting, or criminal matters are not acceptable.
- If a check is "unverified", say which part could not be checked. Never describe the company as clean.

Rules:
- Use only data returned by tools; never invent figures. Note missing or stale data.
- Don't promise returns. Past performance doesn't predict future results.
- End with a one-line reminder that this is educational research, not personalized financial advice,
  and that diversification (e.g. index funds) is often more sensible than betting on a single stock.
"""


def build_agent(model: str = "gpt-5-mini") -> Agent:
    """Create the stock research agent with its tools and system prompt."""
    return Agent(
        chat_generator=OpenAIChatGenerator(model=model),
        tools=[
            rank_stocks,
            get_stock_snapshot,
            get_recent_news,
            check_governance_and_legal,
            get_pestle_analysis,
            get_sector_moves,
        ],
        system_prompt=SYSTEM_PROMPT,
        streaming_callback=print_streaming_chunk,
        max_agent_steps=30,
    )


def main() -> None:
    """Answer a one-off question from the command line, or start an interactive chat."""
    agent = build_agent()
    messages: list[ChatMessage] = []

    if len(sys.argv) > 1:
        agent.run(messages=[ChatMessage.from_user(" ".join(sys.argv[1:]))])
        print()
        return

    print("US stock research agent. Ask e.g. 'What's the best growth stock right now?' (Ctrl+C to quit)\n")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        messages.append(ChatMessage.from_user(question))
        print("\nAgent: ", end="")
        result = agent.run(messages=messages)
        # The agent prepends the system prompt on every run, so drop it from the carried-over history
        messages = [m for m in result["messages"] if not m.is_from(ChatRole.SYSTEM)]
        print()


if __name__ == "__main__":
    main()
