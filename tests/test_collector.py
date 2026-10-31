import json

from geo_visibility.collector import _existing_qids, _redact


def test_existing_qids_skips_errored_records(tmp_path):
    # errored records must re-run on resume, successful ones are skipped
    p = tmp_path / "engine.jsonl"
    p.write_text(
        json.dumps({"qid": "D001", "error": None}) + "\n" +
        json.dumps({"qid": "D002", "error": "connect timeout"}) + "\n" +
        json.dumps({"qid": "D003"}) + "\n" +   # no error key = success
        "corrupted-line\n",                     # invalid JSON ignored
        encoding="utf-8",
    )
    assert _existing_qids(p) == {"D001", "D003"}


def test_redact_strips_api_keys_from_errors():
    msg = "Client error '404' for url 'https://x.test/v1?key=AIzaSecret123.xyz'"
    assert "AIzaSecret123" not in _redact(msg)
    assert "key=***" in _redact(msg)


def test_existing_qids_missing_file(tmp_path):
    assert _existing_qids(tmp_path / "nope.jsonl") == set()
