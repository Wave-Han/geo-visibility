from geo_visibility.models import Brand, Mention, ParsedAnswer
from geo_visibility.report_v1 import (
    action_steps,
    brand_layer_metrics,
    extract_quotes,
    freshness_rate,
    generate_brand_onepager,
    split_engines,
    verdict_line,
)


def brand():
    return Brand(name="iRobot", domain="irobot.com", tier="leader",
                 country="INTL", aliases=["Roomba"])


def make_parsed():
    def p(qid, engine, dim, mentions=None, verdict=None, fresh=None, b=None):
        return ParsedAnswer(qid=qid, engine=engine, dimension=dim, brand=b,
                            mentions=mentions or [], verdict=verdict,
                            freshness_known=fresh)
    return [
        # search layer (deepseek): 1/2 discovery mentions, hedged verdicts
        p("D001", "deepseek", "discovery",
          mentions=[Mention("iRobot", 2, "positive", ["reliable"])], b=None),
        p("D002", "deepseek", "discovery"),
        p("T001", "deepseek", "trust", verdict="hedged", b="iRobot"),
        p("T002", "deepseek", "trust", verdict="hedged", b="iRobot"),
        p("F001", "deepseek", "freshness", fresh=True, b="iRobot"),
        # memory layer (zhipu): 0/1 discovery mentions, positive verdict
        p("D001", "zhipu", "discovery"),
        p("T001", "zhipu", "trust", verdict="positive", b="iRobot"),
    ]


def test_split_and_layer_metrics():
    m = brand_layer_metrics(brand(), split_engines(make_parsed()))
    assert m["search"]["mention"] == 0.5
    assert m["search"]["pos"] == 2.0
    assert m["search"]["verdict"] == {"hedged": 2}
    assert m["search"]["descriptors"] == ["reliable"]
    assert m["memory"]["mention"] == 0.0
    assert m["memory"]["verdict"] == {"positive": 1}
    assert freshness_rate("iRobot", make_parsed()) == 1.0


def test_verdict_line_recognizes_search_newcomer():
    m = {"search": {"mention": 0.62, "verdict": {}, "pos": 2.6},
         "memory": {"mention": 0.0, "verdict": {}, "pos": None}}
    assert "搜索层新贵" in verdict_line("Dreame", m)


def test_verdict_line_double_invisible():
    m = {"search": {"mention": 0.0, "verdict": {}, "pos": None},
         "memory": {"mention": 0.0, "verdict": {}, "pos": None}}
    assert "隐形" in verdict_line("Homeika", m)


def test_action_steps_cap_at_three_with_monitoring():
    m = {"search": {"mention": 0.0, "verdict": {"hedged": 3}, "pos": None},
         "memory": {"mention": 0.0, "verdict": {}, "pos": None}}
    steps = action_steps(m)
    assert len(steps) == 3
    assert any("季度监测" in s for s in steps)


def test_extract_quotes_pulls_brand_sentences_from_trust_answers():
    records = [
        {"engine": "deepseek", "dimension": "trust", "brand": "iRobot",
         "question": "Is iRobot legit?",
         "answer": "iRobot is a legacy brand. The Roomba line is well reviewed. "
                   "Support quality varies by region.",
         "error": None},
        {"engine": "zhipu", "dimension": "discovery", "brand": None,
         "question": "best robot vacuum", "answer": "iRobot makes robots.",
         "error": None},  # discovery answers are not used for quotes
    ]
    # one quote per trust answer; alias sentences count, discovery ignored
    quotes = extract_quotes(brand(), records, max_quotes=2)
    assert len(quotes) == 1
    assert quotes[0]["text"].startswith("iRobot is a legacy brand")
    assert quotes[0]["engine"] == "deepseek"


def test_extract_quotes_prefers_own_trust_questions():
    # a Roborock answer that mentions Ecovacs must NOT become an Ecovacs quote
    ecovacs = Brand(name="Ecovacs", aliases=["Deebot"])
    records = [
        {"engine": "deepseek", "dimension": "trust", "brand": "Roborock",
         "question": "Is Roborock legit?",
         "answer": "Roborock is legit and considered a top competitor to Ecovacs.",
         "error": None},
        {"engine": "deepseek", "dimension": "trust", "brand": "Ecovacs",
         "question": "Is Ecovacs a good brand?",
         "answer": "Ecovacs is a major Chinese robot vacuum maker with strong sales.",
         "error": None},
    ]
    quotes = extract_quotes(ecovacs, records, max_quotes=2)
    assert len(quotes) == 1
    assert quotes[0]["text"].startswith("Ecovacs is a major Chinese")
    assert quotes[0]["question"] == "Is Ecovacs a good brand?"


def test_generate_brand_onepager_standalone():
    html = generate_brand_onepager(brand(), make_parsed(), [])
    assert html.startswith("<!DOCTYPE html>")
    assert "iRobot" in html
    assert "AI 可见性体检页" in html
    # empty records -> graceful no-quote note, not a crash
    assert "本次样本未捕获到直接评论" in html
