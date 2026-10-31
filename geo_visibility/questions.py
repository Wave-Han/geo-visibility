# Build the concrete question set from brands + question templates.
from .models import Brand, Question

# Pilot defaults: one CN leader, one CN emerging, one INTL incumbent -
# enough variety to exercise every metric (mention/citation/engine gap).
PILOT_BRANDS_DEFAULT = ["Roborock", "Homeika", "iRobot"]
PILOT_PER_DIMENSION = {
    "discovery": 6,       # category-level, shared
    "comparison": 1,      # per pilot brand
    "trust": 1,           # per pilot brand
    "price_longtail": 1,  # per pilot brand
    "freshness": 1,       # per pilot brand
}


def load_brands(brands_cfg: dict) -> list[Brand]:
    category = brands_cfg.get("category", "")
    return [
        Brand(
            name=b["name"],
            domain=b.get("domain"),
            tier=b.get("tier", ""),
            country=b.get("country", ""),
            category=category,
            competitors=b.get("competitors", []),
            aliases=b.get("aliases", []),
        )
        for b in brands_cfg.get("brands", [])
    ]


def expand_discovery(q_cfg: dict, limit: int | None = None) -> list[str]:
    """Generate category-level discovery queries from seeds, capped and deduped."""
    d = q_cfg.get("discovery", {})
    limit = limit or d.get("max_questions", 40)
    out: list[str] = []
    subs = d.get("subcategories", [])
    for intent in d.get("intents", ["best"]):
        for sub in subs:
            out.append(f"{intent} {sub}")
            for qual in d.get("qualifiers", []):
                if qual:
                    out.append(f"{intent} {sub} {qual}")
    for sub in subs:
        for price in d.get("budget_prices", []):
            out.append(f"best {sub} under ${price}")
    seen: set[str] = set()
    result: list[str] = []
    for q in out:
        if q not in seen:
            seen.add(q)
            result.append(q)
    return result[:limit]


def _competitor_for(brand: Brand, brands: list[Brand]) -> str:
    for comp in brand.competitors:
        if comp != brand.name:
            return comp
    for other in brands:
        if other.name != brand.name:
            return other.name
    return "competitor"


DIMENSION_PREFIX = {
    "comparison": "C",
    "trust": "T",
    "price_longtail": "P",
    "freshness": "F",
}


def build_question_set(brands: list[Brand], q_cfg: dict) -> list[Question]:
    questions: list[Question] = []
    # Category-level discovery: all brands compete in the same answers.
    for i, text in enumerate(expand_discovery(q_cfg)):
        questions.append(Question(qid=f"D{i + 1:03d}", dimension="discovery", text=text))
    # Brand-level questions rendered from templates.
    counters = {dim: 0 for dim in DIMENSION_PREFIX}
    templates = q_cfg.get("brand_templates", {})
    for brand in brands:
        ctx = {
            "brand": brand.name,
            "competitor": _competitor_for(brand, brands),
            "category": brand.category,
        }
        for dim, prefix in DIMENSION_PREFIX.items():
            for tpl in templates.get(dim, []):
                counters[dim] += 1
                questions.append(
                    Question(
                        qid=f"{prefix}{counters[dim]:03d}",
                        dimension=dim,
                        text=tpl.format(**ctx),
                        brand=brand.name,
                    )
                )
    return questions


def build_pilot_set(brands: list[Brand], questions: list[Question],
                    pilot_brands: list[str] | None = None,
                    per_dimension: dict | None = None):
    """Small pilot: subset of brands + capped questions per dimension.

    Returns (pilot_brands, pilot_questions). Defaults give 6 + 4x3 = 18
    questions per engine - cheap enough to validate pipeline and real cost.
    """
    per_dimension = per_dimension or PILOT_PER_DIMENSION
    names = pilot_brands or PILOT_BRANDS_DEFAULT
    chosen = [b for b in brands if b.name in names]
    known = {b.name for b in chosen}
    result: list[Question] = []
    for dim, cap in per_dimension.items():
        pool = [q for q in questions if q.dimension == dim]
        if dim == "discovery":
            result.extend(pool[:cap])
        else:
            for b in chosen:
                result.extend([q for q in pool if q.brand == b.name][:cap])
    order = {q.qid: i for i, q in enumerate(questions)}
    result.sort(key=lambda q: order[q.qid])
    return chosen, result
