# Shared data models for the visibility pipeline.
from dataclasses import dataclass, field


@dataclass
class Brand:
    name: str
    domain: str | None = None
    tier: str = ""          # leader / growth / emerging / (intl control uses tier too)
    country: str = ""       # CN / INTL
    category: str = ""
    competitors: list[str] = field(default_factory=list)
    # answers often use the product-line name, not the company brand
    # (e.g. "Roomba" for iRobot, "Deebot" for Ecovacs)
    aliases: list[str] = field(default_factory=list)


@dataclass
class Question:
    qid: str                # e.g. D001 (discovery), C001 (comparison), T001 (trust)...
    dimension: str          # discovery / comparison / trust / price_longtail / freshness
    text: str
    brand: str | None = None  # set for brand-level questions


@dataclass
class Mention:
    brand: str
    position: int | None = None   # rank among mentioned brands, 1-based (approximation of list rank)
    sentiment: str = "neutral"    # positive / neutral / negative
    descriptors: list[str] = field(default_factory=list)


@dataclass
class ParsedAnswer:
    qid: str
    engine: str
    dimension: str = ""
    brand: str | None = None            # brand of the question (trust/comparison/etc.)
    mentions: list[Mention] = field(default_factory=list)
    verdict: str | None = None          # trust questions: positive/neutral/negative/hedged
    freshness_known: bool | None = None # freshness questions: does the engine know recent news
