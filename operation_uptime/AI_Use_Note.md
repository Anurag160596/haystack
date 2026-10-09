# How I used AI

I used Claude (Anthropic) as my analyst. It built the Excel model, generated the 8-slide deck directly from the model's values, and researched benchmarks: TalentBait cost per application, IAB and BA labour-market data, Trendence channel reach, Redline social-campaign volumes, StepStone and Pracuj.pl prices, and German hiring-process timings.

How the output was checked:
- Every input carries a linked source or a written derivation; nothing is a bare guess.
- An automated test suite with an independent Python re-implementation ran over 150 scenarios, including edge cases, and changed each of the 218 inputs one at a time. All passed after fixing the bugs it found.
- A deck-vs-model test confirmed the slide figures.

Inputs labelled "Own estimate" are derived by stated arithmetic or rules; I take ownership of them and can defend each line.
