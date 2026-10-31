import asyncio

from geo_visibility.llm import _extract_json
from geo_visibility.models import Brand, Mention, ParsedAnswer
from geo_visibility.parser import build_matchers, llm_parse, merge_semantics, parse_all


def make_matchers():
    return build_matchers([
        Brand(name="iRobot", aliases=["Roomba"]),
        Brand(name="Ecovacs", aliases=["Deebot"]),
        Brand(name="Roborock"),
    ])


def test_extract_json_handles_fences_and_prose():
    fenced = '''Here is the result:
```json
{"mentions": [{"brand": "Roborock"}], "verdict": null}
```'''
    assert _extract_json(fenced)["mentions"][0]["brand"] == "Roborock"
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_llm_parse_maps_aliases_and_verdict():
    async def fake_llm(prompt):
        assert "iRobot/Roomba" in prompt          # aliases listed for the model
        return {
            "mentions": [
                {"brand": "Roomba", "position": 2, "sentiment": "positive",
                 "descriptors": ["reliable"]},
                {"brand": "Unknown Co", "position": 3, "sentiment": "neutral",
                 "descriptors": []},
            ],
            "verdict": "hedged",
            "freshness_known": False,
        }

    record = {"engine": "deepseek", "qid": "T001", "dimension": "trust",
              "brand": "iRobot", "question": "Is iRobot legit?",
              "answer": "The Roomba is solid.", "citations": [], "error": None}
    parsed = asyncio.run(llm_parse(record, make_matchers(), fake_llm))
    # alias Roomba -> canonical iRobot; Unknown Co filtered out
    assert [m.brand for m in parsed.mentions] == ["iRobot"]
    assert parsed.mentions[0].position == 2
    assert parsed.verdict == "hedged"


def test_parse_all_falls_back_to_heuristic_on_llm_failure():
    async def broken_llm(prompt):
        raise RuntimeError("boom")

    records = [
        {"engine": "deepseek", "qid": "T001", "dimension": "trust",
         "brand": "iRobot", "question": "Is iRobot legit?",
         "answer": "iRobot is fine.", "citations": [], "error": None},
        {"engine": "deepseek", "qid": "D001", "dimension": "discovery",
         "brand": None, "question": "best robot vacuum",
         "answer": "", "citations": [], "error": "timeout"},   # skipped entirely
    ]
    parsed = asyncio.run(parse_all(records, make_matchers(), broken_llm))
    assert len(parsed) == 1
    assert parsed[0].mentions[0].brand == "iRobot"


def test_merge_semantics_keeps_regex_mentions_adds_llm_fields():
    # base: regex found 2 mentions (iRobot via alias + Roborock)
    base = [ParsedAnswer(qid="T001", engine="deepseek", dimension="trust",
                         brand="iRobot",
                         mentions=[Mention("iRobot", position=1),
                                   Mention("Roborock", position=2)])]
    # LLM missed one mention but has the semantic fields
    sem = [ParsedAnswer(qid="T001", engine="deepseek", dimension="trust",
                        brand="iRobot",
                        mentions=[Mention("iRobot", position=1,
                                          sentiment="positive",
                                          descriptors=["reliable"])],
                        verdict="hedged", freshness_known=True)]
    merged = merge_semantics(base, sem)
    assert len(merged[0].mentions) == 2            # deterministic mentions kept
    assert merged[0].mentions[0].sentiment == "positive"   # semantics enriched
    assert merged[0].mentions[0].descriptors == ["reliable"]
    assert merged[0].verdict == "hedged"
    assert merged[0].freshness_known is True
