from collections import Counter

from geo_visibility.questions import (
    _competitor_for,
    build_pilot_set,
    build_question_set,
    expand_discovery,
    load_brands,
)
from geo_visibility import config


CFG = config.load_config()


def test_load_brands_reads_tiers_and_competitors():
    brands = load_brands(CFG["brands"])
    assert len(brands) >= 8
    tiers = {b.tier for b in brands}
    assert {"leader", "growth"} <= tiers
    assert {b.country for b in brands} == {"CN", "INTL"}
    assert any(b.competitors for b in brands)


def test_expand_discovery_respects_limit_and_dedupes():
    queries = expand_discovery(CFG["questions"])
    assert len(queries) == CFG["questions"]["discovery"]["max_questions"]
    assert len(set(queries)) == len(queries)
    assert all(q for q in queries)


def test_build_question_set_dimensions_per_brand():
    brands = load_brands(CFG["brands"])
    questions = build_question_set(brands, CFG["questions"])
    dims = {}
    for q in questions:
        dims.setdefault(q.dimension, []).append(q)
    assert dims["discovery"][0].qid == "D001"
    # 4 comparison + 3 trust + 2 price + 1 freshness per brand
    assert len(dims["comparison"]) == 4 * len(brands)
    assert len(dims["trust"]) == 3 * len(brands)
    assert len(dims["price_longtail"]) == 2 * len(brands)
    assert len(dims["freshness"]) == len(brands)
    assert all(q.brand for q in dims["trust"])


def test_competitor_prefers_configured():
    brands = load_brands(CFG["brands"])
    brand = next(b for b in brands if b.competitors)
    comp = _competitor_for(brand, brands)
    usable = [c for c in brand.competitors if c != brand.name]
    if usable:
        assert comp in usable
    else:
        assert comp != brand.name


def test_pilot_set_covers_dimensions_and_brands():
    brands = load_brands(CFG["brands"])
    questions = build_question_set(brands, CFG["questions"])
    chosen, pilot_qs = build_pilot_set(brands, questions)
    assert {b.name for b in chosen} == {"Roborock", "Homeika", "iRobot"}
    dims = Counter(q.dimension for q in pilot_qs)
    assert dims["discovery"] == 6
    # 1 per pilot brand for each brand-level dimension
    assert dims["comparison"] == 3
    assert dims["trust"] == 3
    assert dims["price_longtail"] == 3
    assert dims["freshness"] == 3
    assert all(q.brand in {"Roborock", "Homeika", "iRobot"}
               for q in pilot_qs if q.brand)


def test_pilot_set_custom_brands():
    brands = load_brands(CFG["brands"])
    questions = build_question_set(brands, CFG["questions"])
    chosen, pilot_qs = build_pilot_set(brands, questions,
                                       pilot_brands=["Dreame", "Shark"])
    assert {b.name for b in chosen} == {"Dreame", "Shark"}
    assert all(q.brand in {"Dreame", "Shark"} for q in pilot_qs if q.brand)
