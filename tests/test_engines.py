from geo_visibility.engines import build_engines
from geo_visibility.engines.openai_compat import OpenAICompatEngine
from geo_visibility.engines.openai_responses import OpenAIResponsesEngine


def test_build_engines_skips_missing_keys(monkeypatch):
    cfg = {"engines": {"zhipu": {
        "type": "openai_compat", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash", "api_key_env": "ZHIPU_API_KEY", "enabled": True,
    }}}
    assert build_engines(cfg) == []          # no key -> skipped
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key")
    engines = build_engines(cfg)
    assert len(engines) == 1
    assert engines[0].name == "zhipu"


def test_build_engines_passes_extra_body(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    cfg = {"engines": {"zhipu": {
        "type": "openai_compat", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash", "api_key_env": "ZHIPU_API_KEY", "enabled": True,
        "extra_body": {"tools": [{"type": "web_search", "web_search": {"enable": True}}]},
    }}}
    (engine,) = build_engines(cfg)
    assert isinstance(engine, OpenAICompatEngine)
    assert engine._extra_body["tools"][0]["type"] == "web_search"


def test_build_engines_responses_custom_base_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    cfg = {"engines": {"deepseek": {
        "type": "openai_responses", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-flash", "api_key_env": "DEEPSEEK_API_KEY", "enabled": True,
    }}}
    (engine,) = build_engines(cfg)
    assert isinstance(engine, OpenAIResponsesEngine)
    assert engine.name == "deepseek"          # distinct name -> distinct jsonl file
    assert "api.deepseek.com" in engine._base_url


def test_real_engines_yaml_parses():
    # all engines without keys -> skipped silently, config itself must be valid
    from geo_visibility import config
    assert build_engines(config.load_config()["engines"]) == []
