# Aggregate visibility metrics from parsed answers and raw engine records.
from collections import Counter
from urllib.parse import urlparse

from .models import Brand, ParsedAnswer


def _discovery_pool(parsed: list[ParsedAnswer]) -> list[ParsedAnswer]:
    return [p for p in parsed if p.dimension == "discovery" and p.mentions is not None]


def mention_rate(brand_name: str, parsed: list[ParsedAnswer]) -> float | None:
    """Share of discovery answers that mention the brand. None = no data."""
    pool = _discovery_pool(parsed)
    if not pool:
        return None
    hits = sum(1 for p in pool if any(m.brand == brand_name for m in p.mentions))
    return hits / len(pool)


def avg_position(brand_name: str, parsed: list[ParsedAnswer]) -> float | None:
    positions = [
        m.position
        for p in _discovery_pool(parsed)
        for m in p.mentions
        if m.brand == brand_name and m.position is not None
    ]
    return sum(positions) / len(positions) if positions else None


def sentiment_distribution(brand_name: str, parsed: list[ParsedAnswer]) -> dict[str, int]:
    return dict(
        Counter(
            m.sentiment
            for p in parsed
            for m in p.mentions
            if m.brand == brand_name
        )
    )


def verdict_distribution(brand_name: str, parsed: list[ParsedAnswer]) -> dict[str, int]:
    """Trust-question verdicts for questions about this brand."""
    return dict(
        Counter(
            p.verdict
            for p in parsed
            if p.dimension == "trust" and p.brand == brand_name and p.verdict
        )
    )


def _domain_matches(url: str, domain: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return netloc == domain or netloc.endswith("." + domain)


def citation_rate(brand: Brand, records: list[dict]) -> float | None:
    """Share of raw answers citing the brand's own domain. None = no data/domain."""
    if not records or not brand.domain:
        return None
    hits = sum(
        1
        for r in records
        if any(_domain_matches(u, brand.domain.lower()) for u in r.get("citations", []))
    )
    return hits / len(records)


def citation_source_distribution(records: list[dict]) -> dict[str, int]:
    """Which domains feed the AI answers - the optimization playbook input."""
    counter = Counter(
        urlparse(u).netloc.lower()
        for r in records
        for u in r.get("citations", [])
        if u
    )
    return dict(counter.most_common())


def per_engine_mention_rate(brand_name: str, parsed: list[ParsedAnswer]) -> dict[str, float | None]:
    rates: dict[str, float | None] = {}
    for engine in sorted({p.engine for p in parsed}):
        rates[engine] = mention_rate(brand_name, [p for p in parsed if p.engine == engine])
    return rates


def brand_metrics(brand: Brand, parsed: list[ParsedAnswer], records: list[dict]) -> dict:
    return {
        "name": brand.name,
        "tier": brand.tier,
        "country": brand.country,
        "mention_rate": mention_rate(brand.name, parsed),
        "citation_rate": citation_rate(brand, records),
        "avg_position": avg_position(brand.name, parsed),
        "sentiment": sentiment_distribution(brand.name, parsed),
        "per_engine_mention_rate": per_engine_mention_rate(brand.name, parsed),
    }


def tier_comparison(brands: list[Brand], parsed: list[ParsedAnswer]) -> dict[str, float]:
    """Average mention rate per tier (brands with no data are skipped)."""
    sums: dict[str, list[float]] = {}
    for b in brands:
        rate = mention_rate(b.name, parsed)
        if rate is not None:
            sums.setdefault(b.tier or "unknown", []).append(rate)
    return {tier: sum(v) / len(v) for tier, v in sums.items()}


def country_comparison(brands: list[Brand], parsed: list[ParsedAnswer]) -> dict[str, float]:
    """Average mention rate CN vs INTL - the headline chart of the report."""
    sums: dict[str, list[float]] = {}
    for b in brands:
        rate = mention_rate(b.name, parsed)
        if rate is not None:
            sums.setdefault(b.country or "unknown", []).append(rate)
    return {c: sum(v) / len(v) for c, v in sums.items()}
