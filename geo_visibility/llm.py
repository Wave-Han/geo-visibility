# Thin DeepSeek chat client used as the llm_call for structured parsing.
# Plain chat/completions is enough here (no web search needed for parsing),
# JSON mode on, low temperature for stable extraction.
import asyncio
import json

import httpx


def _extract_json(text: str) -> dict:
    """Robustly pull the JSON object out of a model reply (handles fences)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in reply: {text[:100]!r}")
    return json.loads(text[start:end + 1])


def make_deepseek_llm_call(api_key: str, model: str = "deepseek-chat",
                           base_url: str = "https://api.deepseek.com/v1",
                           retries: int = 2):
    """Return an async llm_call(prompt) -> dict for parser.llm_parse."""
    async def llm_call(prompt: str) -> dict:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{base_url}/chat/completions",
                                             json=body, headers=headers)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return _extract_json(content)
                last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
            except Exception as exc:  # noqa: BLE001 - retry any transport error
                last_exc = exc
            await asyncio.sleep(1 + attempt)
        raise last_exc  # type: ignore[misc]

    return llm_call
