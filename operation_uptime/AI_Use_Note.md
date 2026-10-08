# How I used AI

I used Claude (Anthropic) as my analyst. It built the Excel model, generated the 8-slide deck directly from the model's values, and ran web searches for benchmarks: StepStone and Pracuj.pl prices, Indeed and LinkedIn CPCs, the Appcast apply rate, recognition timelines, WSI wages and plant headcount.

How the AI's output was checked:
- I made accuracy the acceptance bar and asked for every number to be verified before submitting.
- The model was recomputed independently in plain Python and matched the spreadsheet exactly.
- Four separate audit passes checked numbers, dates, formulas and sources. Each fix was re-verified, and inputs were stress-tested on copies.

Rates and volumes labelled "Own estimate" are judgements I take ownership of and can defend line by line.
