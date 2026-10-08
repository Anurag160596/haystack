# How I used AI

I used Claude (Anthropic) as my analyst. It built the Excel model and its formulas, generated the 8-slide deck straight from the model's values, and ran web searches for benchmarks: StepStone and Pracuj.pl prices, Indeed and LinkedIn CPCs, the Appcast apply rate, recognition timelines, WSI wages and plant headcount.

Checks on the AI's output:
- The model was recomputed independently in plain Python and matched the spreadsheet exactly, including the budget-cut scenarios.
- Three separate AI audit passes checked every number, date, formula and citation. Each found real errors, which were fixed. Inputs were stress-tested on copies.
- Every cited figure was re-read on its source page, and weekdays were verified.

Every rate and volume labelled "Own estimate" is a judgement. I own them and can defend them line by line.
