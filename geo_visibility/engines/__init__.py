# Engine factory: builds engines from engines.yaml; keys come from env vars.
# Engines without a configured key are skipped silently so partial runs work.
import os

from .base import Engine
from .gemini import GeminiEngine
from .openai_compat import OpenAICompatEngine
from .openai_responses import OpenAIResponsesEngine


def build_engines(cfg: dict) -> list[Engine]:
    engines: list[Engine] = []
    for name, spec in (cfg.get("engines") or {}).items():
        if not spec.get("enabled", True):
            continue
        api_key = os.environ.get(spec.get("api_key_env", ""), "")
        if not api_key:
            continue
        kind = spec["type"]
        if kind == "openai_responses":
            engines.append(OpenAIResponsesEngine(
                name, spec["model"], api_key, base_url=spec.get("base_url")))
        elif kind == "openai_compat":
            engines.append(OpenAICompatEngine(
                name, spec["base_url"], spec["model"], api_key,
                extra_body=spec.get("extra_body")))
        elif kind == "gemini":
            engines.append(GeminiEngine(spec["model"], api_key))
        else:
            raise ValueError(f"unknown engine type: {kind}")
    return engines
