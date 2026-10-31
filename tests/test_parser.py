from geo_visibility.models import Brand
from geo_visibility.parser import build_matchers, heuristic_mentions, parse_record_heuristic


def make_matchers():
    return build_matchers([
        Brand(name="iRobot", aliases=["Roomba"]),
        Brand(name="Ecovacs", aliases=["Deebot"]),
        Brand(name="Roborock"),
    ])


def test_finds_brands_case_insensitive_with_position():
    answer = (
        "For most homes, Roborock is the top pick. "
        "The Roomba j9 is the classic choice, and Ecovacs sits third."
    )
    mentions = {m.brand: m for m in heuristic_mentions(answer, make_matchers())}
    # order by first appearance: Roborock, Roomba->iRobot, Ecovacs
    assert list(mentions) == ["Roborock", "iRobot", "Ecovacs"]
    assert [mentions[b].position for b in ("Roborock", "iRobot", "Ecovacs")] == [1, 2, 3]


def test_alias_counts_as_canonical_brand():
    # answer mentioning ONLY "Roomba" must still count as an iRobot mention
    answer = "The Roomba Combo Essential is the best budget pick."
    assert [m.brand for m in heuristic_mentions(answer, make_matchers())] == ["iRobot"]


def test_no_mention_returns_empty():
    assert heuristic_mentions("No brands mentioned here.", make_matchers()) == []


def test_word_boundary_prevents_partial_match():
    assert heuristic_mentions("Robotucky is a different thing.", make_matchers()) == []


def test_parse_record_heuristic_maps_fields():
    record = {
        "engine": "deepseek",
        "qid": "T001",
        "dimension": "trust",
        "brand": "iRobot",
        "question": "Is iRobot legit?",
        "answer": "Yes, iRobot is generally considered legit.",
        "citations": [],
        "error": None,
    }
    parsed = parse_record_heuristic(record, make_matchers())
    assert parsed.qid == "T001"
    assert parsed.engine == "deepseek"
    assert parsed.dimension == "trust"
    assert parsed.brand == "iRobot"
    assert [m.brand for m in parsed.mentions] == ["iRobot"]
