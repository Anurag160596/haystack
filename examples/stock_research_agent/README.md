# US Stock Research Agent

A [Haystack](https://haystack.deepset.ai) `Agent` that helps you work out which US stock looks best **for your goals**,
and explains why.

There is no single "best stock". The agent asks (or assumes) your profile — `balanced`, `growth`, `value`,
`income` or `low_risk` — then:

1. **Reads the market** (`get_sector_moves`): each sector's 1-month to 1-year return against the S&P 500, to see
   which industries have a tailwind and which are under pressure.
2. **Ranks candidates** (`rank_stocks`): your tickers, or a default screen of 30 large caps. Each stock gets 0-100
   scores, relative to the others, on growth, profitability, valuation (including EV/EBITDA and free-cash-flow
   yield), momentum (including its sector's trend), safety and dividend yield. The scores are then weighted by
   your profile.
3. **Checks governance and legal standing** (`check_governance_and_legal`). This is non-negotiable:
   - **SEC filings, last 2 years.** Restatements (8-K item 4.02), late annual or quarterly reports (NT 10-K /
     NT 10-Q) and bankruptcy filings (item 1.03) are **red**. A red stock is removed from rankings and is never
     recommended. Auditor changes (item 4.01) and delisting notices or exchange transfers (item 3.01) are
     **amber**.
   - **ISS governance risk scores** from Yahoo Finance. An overall score of 8/10 or more is amber.
   - **Legal and regulatory headlines, last 90 days.** Misconduct-type headlines (fraud, criminal charges,
     accounting problems, subpoenas and so on) are amber.

   The agent must explain every amber flag before recommending a stock. It can't call a company clean if any
   check couldn't run ("unverified").
4. **Scans the industry with PESTLE** (`get_pestle_analysis`): recent political, economic, social, technological,
   legal and environmental headlines. The agent labels each point as a tailwind or a headwind.
5. **Looks closer at the leaders** (`get_stock_snapshot`, `get_recent_news`).
6. **Explains** its top pick, the runners-up, the governance status, the industry tailwinds and headwinds, and
   the risks, in plain language.

Data sources are all free:
- prices and fundamentals: Yahoo Finance via `yfinance`
- filings: SEC EDGAR
- headlines: Google News RSS

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
export SEC_USER_AGENT="Your Name you@example.com"   # SEC EDGAR requires a contact email
python stock_agent.py                                   # interactive chat
python stock_agent.py "Best income stock among KO, PEP, PG, JNJ?"
```

To use a different model, change `build_agent(model=...)`. You can also swap `OpenAIChatGenerator` for any Haystack
chat generator that supports tools.

The automated checks are a screen, not a full legal review: headline searches can miss cases, and they can also
flag ones that aren't serious. Read the company's latest 10-K "Legal Proceedings" and "Risk Factors" sections
before investing.

> Educational research only, not financial advice. Past performance does not predict future results.
