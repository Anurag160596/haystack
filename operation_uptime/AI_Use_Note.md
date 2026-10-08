# How I used AI

I used Claude (Anthropic) as my analyst. It built the model structure, wrote the Excel formulas, drafted the memo, and ran web searches for benchmarks. Those benchmarks were StepStone and Pracuj.pl ad prices, Indeed and LinkedIn CPC ranges, the Appcast apply rate, recognition timelines, WSI wages and plant headcount.

Checks on the AI's output:
- The model was recomputed independently in plain Python, and it matched the spreadsheet exactly.
- A second AI pass audited every memo number, date and citation, and found real errors. They were fixed: fixed costs left out of the channel ranking, cash timing, test sizes and a tracker bug.
- Every cited figure was re-read on its source page. Weekdays were verified.

All rates and volumes labelled "Own estimate" are judgements. I own them and can defend them line by line.
