# geo-visibility

![tests](https://github.com/Wave-Han/geo-visibility/actions/workflows/tests.yml/badge.svg)

**Measure how brands appear in AI answer engines — reproducibly.**

> Also available: [geo-visibility-mcp](https://github.com/Wave-Han/geo-visibility-mcp) — a Java/Spring MCP server exposing the same measurement as agent tools (shared data format).

Buyers increasingly ask ChatGPT, Perplexity, Gemini or DeepSeek before they buy. Teams already track SEO rankings, but few can answer a simpler question: *when someone asks an AI for a recommendation in my category, is my brand mentioned — and how?*

This is a small, tested Python toolkit for measuring that. It asks a configurable set of buyer questions across multiple AI engines, records the raw answers, extracts brand mentions and trust verdicts, and renders an HTML report with per-brand pages.

> Independent research tool. It only calls official provider APIs, stores no client data, and is not a commercial service.

## Why two layers

During development one engine was configured with a web-search tool but answered from training memory anyway ("As of my last update…", recommending 2022 models). That produced a useful distinction:

| Layer | What it measures | How to detect it |
|---|---|---|
| **Search layer** | What the engine recommends *today*, from live retrieval | Citations / grounding metadata present; current-year models named |
| **Memory layer** | What the engine *remembers* from training data | No retrieval artifacts; dated answers |

Mixing the two silently corrupts results. The toolkit keeps them separate, and includes `probe_zhipu.py` to verify whether an engine actually executes its search tool before you trust its output.

## What it measures

Five question dimensions are generated per brand:

| Dimension | Example | Purpose |
|---|---|---|
| Discovery | "best robot vacuum for pet hair" | Whether you appear in default recommendations at all |
| Comparison | "{brand} vs {competitor}" | Who the engine positions you against |
| Trust | "Is {brand} legit?" | The verdict the engine gives when asked directly |
| Price | "Is {brand} worth the money?" | Value positioning |
| Freshness | "What's new from {brand} in 2025-2026?" | Whether the engine knows recent launches |

Metrics per brand: mention rate, average position, trust-verdict distribution (positive / neutral / negative / hedged), freshness-awareness rate, recurring descriptors, and citation-source distribution when the engine returns citations.

See [`docs/methodology.md`](docs/methodology.md) for sampling design, metric definitions and limitations.

## Quick start

```bash
pip install -r requirements.txt

# Set at least one key. Engines without a key are skipped automatically.
export DEEPSEEK_API_KEY="..."
# or OPENAI_API_KEY / PERPLEXITY_API_KEY / GEMINI_API_KEY / ZHIPU_API_KEY / DASHSCOPE_API_KEY

# 1. Cheap pilot: 3 brands x 18 questions (~seconds to a couple of minutes)
python -m geo_visibility collect --pilot

# 2. Parse (heuristic, free & deterministic)
python -m geo_visibility parse --dir raw_pilot

# 3. Optional: LLM semantics for verdicts/sentiment (uses deepseek-chat)
python -m geo_visibility parse --dir raw_pilot --llm

# 4. Report
python -m geo_visibility report --dir raw_pilot      # summary table
python -m geo_visibility full-report --dir raw_pilot # 8-section report + per-brand pages
```

Full run: `python -m geo_visibility collect` (all brands × all questions).

Export a standalone single-brand page:

```bash
python -m geo_visibility onepager --names "BrandA,BrandB"
```

## Supported engines

| Engine | Transport | Search grounding | Notes |
|---|---|---|---|
| `chatgpt` | OpenAI Responses API | `web_search` tool | |
| `perplexity` | OpenAI-compatible | built in | returns a `citations` list |
| `gemini` | generateContent | `google_search` | citations from `groundingMetadata` |
| `deepseek` | OpenAI Responses API | `web_search` | web search only on `/v1/responses` |
| `zhipu` | OpenAI-compatible | `web_search` tool | free `glm-4-flash` may not execute it — verify |
| `qwen` | OpenAI-compatible | `enable_search` | Aliyun Bailian |
| `grok` | OpenAI-compatible | — | disabled by default |

Provider models change frequently. Verify model names in `data/engines.yaml` before a run.

## Design decisions worth knowing

- **Mentions are counted deterministically (regex + aliases); LLMs only supply semantics.** An LLM parser under-counts mentions it considers unimportant, so its numbers drift between runs. The toolkit merges both: reproducible mention rate, richer verdicts. See `parser.merge_semantics`.
- **Aliases matter.** Answers say "Roomba" for iRobot and "Deebot" for Ecovacs. Brands accept an `aliases` list in `data/brands.yaml`.
- **Failed calls are re-run on resume.** JSONL is append-only; errored records are excluded from the resume set instead of being silently treated as done.
- **Keys never travel in URLs**, and error strings are redacted before being written to disk.
- **Errors carry the response body excerpt**, so provider failures ("model retired", "quota") are visible instead of a bare status code.

## Architecture

```
data/brands.yaml ─┐
data/questions.yaml ┼─→ questions.py ─→ collector.py ─→ output/raw/<engine>.jsonl
data/engines.yaml ─┘                         │
                                             ▼
                              parser.py (regex mentions + optional LLM semantics)
                                             │
                                             ▼
                                 analysis.py ─→ report.py / report_v1.py
```

```
geo_visibility/
  engines/        provider adapters (official APIs + search grounding)
  questions.py    question generation from brands × templates
  collector.py    concurrency, retries, resume-safe JSONL
  parser.py       deterministic mentions + LLM structured parsing
  analysis.py     mention rate / position / verdict / citation metrics
  report.py       summary HTML
  report_v1.py    full report + per-brand pages
  llm.py          small JSON-mode client used for parsing
```

## Tests

```bash
python -m pytest -q
```

38 tests cover question generation, alias matching, metric math, resume behavior, key redaction, LLM-parse fallbacks and report rendering. CI runs on Python 3.10 and 3.12.

## Limitations

- API behavior is not identical to the consumer web UI.
- Discovery questions are a sample, not the whole category; treat rates as relative, not absolute.
- "Position" approximates rank by order of first appearance in the answer.
- Free tiers may silently answer from memory — run `probe_zhipu.py` (or inspect citations) before trusting an engine.
- Engines update models often; a quarterly re-run is needed for time series.

## 中文简介

一个小型、可测试的 Python 工具包，用于测量品牌在 AI 回答引擎中的可见性：按 5 类买家问题批量询问多个引擎，记录原始回答，抽取提及率、排位、信任裁决与新鲜度，并生成带单品牌页的 HTML 报告。

核心设计：**搜索层 / 记忆层分开测量**（前者反映实时推荐，后者反映训练语料）；提及率用确定性正则计算、语义字段用 LLM 抽取；支持断点续跑、别名匹配与密钥脱敏。详见 [`docs/methodology.md`](docs/methodology.md)。

## License

MIT
