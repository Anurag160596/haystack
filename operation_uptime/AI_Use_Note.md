# How I used AI

I used Claude (Anthropic) as my analyst. It built the Excel model, generated the 8-slide deck directly from the model's values, and ran web searches for benchmarks: StepStone and Pracuj.pl prices, Indeed and LinkedIn CPCs, the Appcast apply rate, recognition timelines, WSI wages and plant headcount.

How the output was checked:
- I made accuracy the acceptance bar.
- Independent audit passes checked numbers, dates, formulas and sources.
- An automated test suite, with an independent Python re-implementation, ran 93 scenarios including edge cases (zero capacity, zero openings, impossible deadlines). All passed after fixing the bugs it found.
- A deck-vs-model test confirmed the slide figures.

Rates and volumes labelled "Own estimate" are judgements I take ownership of and can defend line by line.
