# Extract brand mentions / sentiment / position from raw answers.
# heuristic_mentions works offline (regex-based, no LLM needed);
# llm_parse accepts an injected async llm_call(prompt) -> dict for higher quality.
import asyncio
import re

from .models import Mention, ParsedAnswer


def parsed_from_json(data: list[dict]) -> list[ParsedAnswer]:
    """Rebuild ParsedAnswer objects from a persisted parsed_*.json file."""
    out = []
    for x in data:
        out.append(ParsedAnswer(
            qid=x["qid"],
            engine=x["engine"],
            dimension=x.get("dimension", ""),
            brand=x.get("brand"),
            mentions=[Mention(**m) for m in x.get("mentions", [])],
            verdict=x.get("verdict"),
            freshness_known=x.get("freshness_known"),
        ))
    return out


def build_matchers(brands) -> list[tuple[str, re.Pattern, str]]:
    """One matcher per brand: (canonical_name, regex, display_variants).

    Matches the canonical name OR any alias (e.g. Roomba -> iRobot),
    case-insensitive, word-boundary.
    """
    matchers = []
    for b in brands:
        names = [b.name] + list(getattr(b, "aliases", []) or [])
        pattern = re.compile(rf"\b(?:{'|'.join(re.escape(n) for n in names)})\b",
                             re.IGNORECASE)
        variants = "/".join(names)
        matchers.append((b.name, pattern, variants))
    return matchers


def heuristic_mentions(answer: str,
                       matchers: list[tuple[str, re.Pattern, str]]) -> list[Mention]:
    """Find brands by word-boundary match; position = order of first appearance."""
    found: list[tuple[int, str]] = []
    for name, pattern, _ in matchers:
        m = pattern.search(answer)
        if m:
            found.append((m.start(), name))
    found.sort()
    return [Mention(brand=name, position=i + 1) for i, (_, name) in enumerate(found)]


def parse_record_heuristic(record: dict,
                           matchers: list[tuple[str, re.Pattern, str]]) -> ParsedAnswer:
    mentions = heuristic_mentions(record.get("answer", ""), matchers)
    return ParsedAnswer(
        qid=record["qid"],
        engine=record["engine"],
        dimension=record.get("dimension", ""),
        brand=record.get("brand"),
        mentions=mentions,
    )


LLM_PROMPT = """You analyze an AI search engine answer for brand visibility research.
Question: {question}
Answer: {answer}
Brands of interest (aliases count as the brand): {brands}
Return strict JSON only:
{{"mentions": [{{"brand": "<one of the brands or aliases above>", "position": <int rank in recommendation list or null>, "sentiment": "positive|neutral|negative", "descriptors": ["<words the answer uses about this brand>"]}}], "verdict": "<for 'is X legit/good' questions: positive|neutral|negative|hedged, else null>", "freshness_known": <bool or null>}}"""


async def llm_parse(record: dict,
                    matchers: list[tuple[str, re.Pattern, str]],
                    llm_call) -> ParsedAnswer:
    """llm_call: async fn(prompt) -> dict of the JSON structure above."""
    alias_to_canonical = {}
    brands_line = []
    for name, _, variants in matchers:
        brands_line.append(variants)
        for v in variants.split("/"):
            alias_to_canonical[v] = name
    prompt = LLM_PROMPT.format(
        question=record["question"],
        answer=record.get("answer", ""),
        brands=", ".join(brands_line),
    )
    data = await llm_call(prompt)
    mentions = [
        Mention(
            brand=alias_to_canonical.get(m.get("brand", ""), m.get("brand", "")),
            position=m.get("position"),
            sentiment=m.get("sentiment", "neutral"),
            descriptors=m.get("descriptors", []),
        )
        for m in data.get("mentions", [])
        if alias_to_canonical.get(m.get("brand", ""))
    ]
    return ParsedAnswer(
        qid=record["qid"],
        engine=record["engine"],
        dimension=record.get("dimension", ""),
        brand=record.get("brand"),
        mentions=mentions,
        verdict=data.get("verdict"),
        freshness_known=data.get("freshness_known"),
    )


async def parse_all(records: list[dict],
                    matchers: list[tuple[str, re.Pattern, str]],
                    llm_call=None,
                    concurrency: int = 4) -> list[ParsedAnswer]:
    """Parse records; LLM when available (falls back to heuristic per record)."""
    sem = asyncio.Semaphore(concurrency)

    async def one(r: dict) -> ParsedAnswer:
        if llm_call is not None:
            async with sem:
                try:
                    return await llm_parse(r, matchers, llm_call)
                except Exception:  # noqa: BLE001 - one bad record falls back
                    pass
        return parse_record_heuristic(r, matchers)

    ok = [r for r in records if r.get("answer") and not r.get("error")]
    return list(await asyncio.gather(*(one(r) for r in ok)))


def merge_semantics(base: list[ParsedAnswer],
                    sem: list[ParsedAnswer]) -> list[ParsedAnswer]:
    """Deterministic mentions (regex base) + LLM semantic fields.

    Mention rate and position must stay reproducible (regex, same numbers as
    published articles); the LLM only contributes what regex cannot extract:
    verdicts, freshness, sentiment, descriptors. Keeps both pipelines honest.
    """
    sem_by = {(p.engine, p.qid): p for p in sem}
    for p in base:
        s = sem_by.get((p.engine, p.qid))
        if not s:
            continue
        rich = {m.brand: m for m in s.mentions}
        for m in p.mentions:
            r = rich.get(m.brand)
            if r:
                m.sentiment = r.sentiment
                m.descriptors = r.descriptors
        p.verdict = s.verdict
        p.freshness_known = s.freshness_known
    return base
