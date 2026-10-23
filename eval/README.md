# Evaluation

95 questions with ground truth computed from DuckDB, scored twice: once on what
retrieval handed the model, once on what the model wrote.

```bash
make eval-set         # rebuild eval_set.json from the current data
make eval-retrieval   # score retrieval only - no LLM calls
make eval             # full run against the configured LLM (resumable)
pytest eval/          # tests for the scorer itself
```

## Questions

| Type | n | Expected |
|------|---|----------|
| `yield_lookup` | 15 | Gross yield (±0.1 pts), next to the community |
| `yield_unavailable` | 5 | Declines; states no yield for that community |
| `compare_yield` | 10 | Both yields, each next to its community |
| `recommendation` | 12 | INVEST/HOLD label and score |
| `price_by_bedrooms` | 10 | Median ready price for the unit type (±1.5%) |
| `price_per_sqft` | 8 | Median ready AED/sqft (±1.5%) |
| `momentum` | 8 | Same-project change Q1→Q3 (±0.2 pts) |
| `supply_risk` | 8 | LOW / MEDIUM / HIGH |
| `ranking` | 6 | Highest/lowest yield, top scores, cheapest, most sales |
| `budget_filter` | 5 | Correct bedroom/price/community filters |
| `out_of_scope` | 8 | Declines: villas, DAMAC Hills 2, developers, service charges, 2024 prices |

Questions use the aliases people type (JVC, DSO, downtown), so filter
extraction is tested along the way. `build_eval_set.py` fails loudly if the
data can no longer answer a question (e.g. a community loses its yield).

## Scoring (`scoring.py`)

- A number or label only counts in a segment (line, table row, sentence) that
  names its community, so Marina's 5.81% can't satisfy a question about JVC.
  An answer with one expected community may name it once and give the figure
  in the next sentence; the retrieval context must always pair them.
- Sample-sale lines never count as a community figure: a single sale at
  AED 970,000 sitting within tolerance of a 997,700 median is a coincidence.
- A refusal must be near the community, and any yield stated for a community
  without one fails the question, hedged or not.
- Answers naming a well-known community the data doesn't have fail. Citing DLD
  is tracked as a rate, not required to pass.

## Retrieval baseline (no LLM)

86% of 95 questions (October 2026 data). The failures are real retrieval gaps:

| Type | Pass | Cause |
|------|------|-------|
| `price_by_bedrooms` | 2/10 | The report's Prices section isn't among the 3 semantic hits; the summary, yield and supply sections outrank it |
| `yield_unavailable` | 2/5 | Communities without a yield still show per-sale "estimated yield" figures from project-level rents |
| `ranking` | 4/6 | Unfiltered questions see only the top 8 communities by score; JVC (most sales) and Palm Jumeirah (lowest yield) rank below that |

Two scorer bugs were found and fixed while setting the baseline (the first run
read 96%): sample sales matched medians by coincidence, and a one-community
question matched another community's row. Both have regression tests.

`archive/` holds the v1 set and results, which were measured on the generated
dataset the app used before DLD data.
