# US Stock Research Agent

A [Haystack](https://haystack.deepset.ai) `Agent` that helps you work out which US stock looks best **for your goals**,
and explains why.

There is no single "best stock". The agent asks (or assumes) your profile — `balanced`, `growth`, `value`,
`income` or `low_risk` — then:

1. **Ranks candidates** (`rank_stocks`): your tickers, or a default screen of 30 large caps. Each stock gets 0-100
   scores, relative to the others, on growth, profitability, valuation, momentum, safety and dividend yield.
   The scores are then weighted by your profile.
2. **Looks closer at the leaders** (`get_stock_snapshot`, `get_recent_news`): P/E, PEG, margins, debt, returns,
   volatility, drawdown, analyst targets and headlines.
3. **Explains** its top pick, the runners-up and the risks in plain language.

Market data comes from Yahoo Finance via `yfinance`, which is free and needs no key.

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
python stock_agent.py                                   # interactive chat
python stock_agent.py "Best income stock among KO, PEP, PG, JNJ?"
```

To use a different model, change `build_agent(model=...)`. You can also swap `OpenAIChatGenerator` for any Haystack
chat generator that supports tools.

> Educational research only, not financial advice. Past performance does not predict future results.
