from geo_visibility import analysis
from geo_visibility.models import Brand, Mention, ParsedAnswer


def make_parsed(qid, engine="perplexity", dimension="discovery", brand=None, mentions=None, verdict=None):
    return ParsedAnswer(qid=qid, engine=engine, dimension=dimension,
                        brand=brand, mentions=mentions or [], verdict=verdict)


def test_mention_rate_over_discovery_only():
    parsed = [
        make_parsed("D001", mentions=[Mention("Petlibro", position=1)]),
        make_parsed("D002", mentions=[Mention("Petkit", position=1), Mention("Petlibro", position=2)]),
        make_parsed("D003", mentions=[Mention("Petkit", position=1)]),
        make_parsed("C001", dimension="comparison", mentions=[Mention("Petlibro")]),  # excluded
    ]
    assert analysis.mention_rate("Petlibro", parsed) == 2 / 3


def test_mention_rate_none_when_no_data():
    assert analysis.mention_rate("Petlibro", []) is None
    assert analysis.mention_rate("Petlibro", [make_parsed("C001", dimension="comparison")]) is None


def test_avg_position():
    parsed = [
        make_parsed("D001", mentions=[Mention("Petlibro", position=1)]),
        make_parsed("D002", mentions=[Mention("Petkit", position=1), Mention("Petlibro", position=3)]),
    ]
    assert analysis.avg_position("Petlibro", parsed) == 2.0


def test_verdict_distribution_filters_by_brand():
    parsed = [
        make_parsed("T001", dimension="trust", brand="Petlibro", verdict="positive"),
        make_parsed("T002", dimension="trust", brand="Petlibro", verdict="hedged"),
        make_parsed("T003", dimension="trust", brand="Petkit", verdict="negative"),
    ]
    assert analysis.verdict_distribution("Petlibro", parsed) == {"positive": 1, "hedged": 1}


def test_citation_rate_matches_root_and_subdomain():
    brand = Brand(name="Petlibro", domain="petlibro.com")
    records = [
        {"citations": ["https://www.petlibro.com/pages/about", "https://reddit.com/r/cats"]},
        {"citations": ["https://help.petlibro.com/faq"]},
        {"citations": ["https://petkit.com/"]},
        {"citations": []},
    ]
    assert analysis.citation_rate(brand, records) == 0.5


def test_citation_rate_none_without_domain_or_records():
    assert analysis.citation_rate(Brand(name="X"), [{}]) is None
    assert analysis.citation_rate(Brand(name="X", domain="x.com"), []) is None


def test_citation_source_distribution_counts_domains():
    records = [
        {"citations": ["https://www.reddit.com/r/CatAdvice", "https://www.reddit.com/r/cats"]},
        {"citations": ["https://www.nytimes.com/wirecutter/reviews/litter-boxes"]},
    ]
    dist = analysis.citation_source_distribution(records)
    assert dist["www.reddit.com"] == 2
    assert dist["www.nytimes.com"] == 1


def test_tier_and_country_comparison():
    brands = [
        Brand(name="Petlibro", tier="growth", country="CN"),
        Brand(name="Petkit", tier="leader", country="CN"),
        Brand(name="Litter-Robot", tier="leader", country="INTL"),
    ]
    parsed = [
        make_parsed("D001", mentions=[Mention("Petlibro")]),
        make_parsed("D002", mentions=[Mention("Petlibro"), Mention("Petkit"), Mention("Litter-Robot")]),
    ]
    tiers = analysis.tier_comparison(brands, parsed)
    assert tiers["growth"] == 1.0
    assert tiers["leader"] == 0.5
    countries = analysis.country_comparison(brands, parsed)
    assert countries["CN"] == 0.75
    assert countries["INTL"] == 0.5


def test_per_engine_mention_rate_reveals_engine_gap():
    parsed = [
        make_parsed("D001", engine="chatgpt", mentions=[Mention("Petlibro")]),
        make_parsed("D002", engine="chatgpt", mentions=[]),
        make_parsed("D001", engine="gemini", mentions=[]),
        make_parsed("D002", engine="gemini", mentions=[]),
    ]
    rates = analysis.per_engine_mention_rate("Petlibro", parsed)
    assert rates == {"chatgpt": 0.5, "gemini": 0.0}
