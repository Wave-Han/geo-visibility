# Methodology

This document describes the measurement design, so results can be reproduced or adapted to a different category.

## 1. Sampling

- Pick **one category** per study. Cross-category averages are not meaningful.
- Build a brand sample in tiers, because tier contrast is the interesting signal:

| Tier | Target | Typical selection rule |
|---|---|---|
| Leaders | ~8 | Top share / strongest brand awareness |
| Growth | ~15-20 | Established mid-tier, marketplace-native |
| Emerging | ~10 | Started within the last 2-3 years, social-commerce driven |
| International control | ~6-8 | Non-domestic incumbents, used for comparison |

- Add a small international control group. "Domestic vs international" is usually the strongest comparative finding.
- Verify every domain manually before a production run. Search results contain stale and wrong domains.
- Record product-line names as aliases: answers often use "Roomba" instead of "iRobot", "Deebot" instead of "Ecovacs".

## 2. Question set

Five dimensions, generated from templates (`data/questions.yaml`):

| Dimension | Count | Purpose |
|---|---|---|
| Discovery | ~40 category-level questions | Default-recommendation visibility |
| Comparison | 4 per brand | Positioning against competitors |
| Trust | 3 per brand | Direct credibility verdict |
| Price | 2 per brand | Value framing |
| Freshness | 1 per brand | Knowledge of recent launches |

Discovery questions are generated from `intent × subcategory × qualifier` plus budget variants, then de-duplicated and capped. Keep them sounding like real buyer queries; unnatural phrasing produces unnatural answers.

## 3. Two-layer engine model

Before measuring, establish whether each engine actually performs retrieval:

- **Search layer**: live retrieval. Evidence: citation/grounding metadata, current-year products, no "as of my last update" phrasing.
- **Memory layer**: training-data recall. Evidence: no retrieval artifacts, dated answers, defunct products still recommended.

Do not average across layers. Report them separately: the gap between "remembered" and "recommended today" is the actionable finding.

`probe_zhipu.py` is a minimal probe: it asks a current-events question and prints the response structure. If the response has no search artifact, treat the engine as a memory-layer engine.

## 4. Metrics

| Metric | Definition | Notes |
|---|---|---|
| Mention rate | Share of discovery answers naming the brand (incl. aliases) | Deterministic regex |
| Average position | Mean of first-appearance rank among mentioned brands | Approximation of list rank |
| Trust verdict | Distribution of positive / neutral / negative / hedged on trust questions | LLM-extracted, validated against a sample |
| Freshness awareness | Share of freshness answers demonstrating post-cutoff knowledge | LLM-extracted |
| Descriptors | Recurring words the answer uses about the brand | LLM-extracted |
| Citation sources | Domains cited across answers | Only when the engine returns citations |

**Why mentions are not LLM-parsed:** in testing, an LLM parser systematically under-counted mentions it judged unimportant, producing mention rates that diverged from deterministic matching (and between runs). The toolkit therefore uses regex for counts and LLMs only for semantic fields. If you change this, publish the parser version with your numbers.

## 5. Execution

- Collect: concurrent requests with retry, append-only JSONL per engine, resume on interruption.
- Failed records are retried on resume; they are never treated as completed.
- Parse: deterministic mentions first, optional LLM semantics second (`parse --llm`).
- Report: summary table and full report are both generated from the same parsed data.

## 6. Known limitations

1. **API ≠ consumer UI.** Results can differ from what a user sees in the web app.
2. **Sample size.** ~40 discovery questions gives directional, not absolute, rates.
3. **Position approximation.** First-appearance order is not an explicit ranking.
4. **Model churn.** Providers retire and rename models; pin and verify model names.
5. **Non-determinism.** Repeated identical prompts can yield different answers; run enough questions and report the denominator.
6. **Free tiers.** Some free tiers do not include retrieval; verify before measuring.
7. **Brand attribution.** Product-line names, misspellings and indirect references require an alias list; without it, leaders are undercounted.

## 7. Adapting to another category

1. Replace `category` and subcategory/qualifier seeds in `data/questions.yaml`.
2. Replace the brand list in `data/brands.yaml` (keep the tier structure).
3. Verify engines with a probe; record which layer each one measures.
4. Run a pilot (`collect --pilot`), inspect raw answers by hand, then scale.
5. Re-run quarterly to build a time series — the trend is more useful than any single snapshot.
