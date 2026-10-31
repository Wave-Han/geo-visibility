# Minimal HTML summary renderer (v0 - one table + citation sources).
# The full report structure (8 sections, per-brand pages) lives in DESIGN.md.
from . import analysis
from .models import Brand, ParsedAnswer


def _fmt_rate(rate: float | None) -> str:
    return f"{rate:.0%}" if rate is not None else "-"


def _fmt_pos(pos: float | None) -> str:
    return f"{pos:.1f}" if pos is not None else "-"


_VERDICT_SHORT = {"positive": "pos", "neutral": "neu", "negative": "neg", "hedged": "hedged"}


def _fmt_verdict(dist: dict[str, int]) -> str:
    if not dist:
        return "-"
    return " ".join(f"{_VERDICT_SHORT.get(k, k)}{v}" for k, v in dist.items())


def render_summary_html(brands: list[Brand], parsed: list[ParsedAnswer],
                        records: list[dict]) -> str:
    rows = []
    ranked = sorted(brands, key=lambda b: -(analysis.mention_rate(b.name, parsed) or 0))
    for b in ranked:
        m = analysis.brand_metrics(b, parsed, records)
        per_engine = ", ".join(
            f"{e}: {_fmt_rate(r)}" for e, r in m["per_engine_mention_rate"].items()
        )
        verdict = _fmt_verdict(analysis.verdict_distribution(b.name, parsed))
        rows.append(
            f"<tr><td>{b.name}</td><td>{b.tier}</td><td>{b.country}</td>"
            f"<td>{_fmt_rate(m['mention_rate'])}</td><td>{_fmt_rate(m['citation_rate'])}</td>"
            f"<td>{_fmt_pos(m['avg_position'])}</td><td>{verdict}</td><td>{per_engine}</td></tr>"
        )
    sources = analysis.citation_source_distribution(records)
    source_rows = "".join(
        f"<tr><td>{domain}</td><td>{count}</td></tr>"
        for domain, count in list(sources.items())[:20]
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Visibility Summary (v0)</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; margin-bottom: 2rem; }}
td, th {{ border: 1px solid #ccc; padding: 6px 12px; text-align: left; }}
th {{ background: #f5f5f5; }}
</style></head><body>
<h1>AI Visibility Summary (v0)</h1>
<table>
<tr><th>Brand</th><th>Tier</th><th>Country</th><th>Mention rate</th>
<th>Citation rate</th><th>Avg position</th><th>AI trust verdict</th><th>Per-engine mention</th></tr>
{''.join(rows)}
</table>
<h2>Top citation sources (what feeds the AI answers)</h2>
<table><tr><th>Domain</th><th>Citations</th></tr>{source_rows}</table>
<p style="color:#888;font-size:0.85em">* zhipu answers come from model memory
(free glm-4-flash does not execute web_search - verified by probe_zhipu.py),
so its column measures memory-layer visibility; deepseek measures live-search
visibility. Do not quote pooled rates without the per-engine split.</p>
</body></html>"""
