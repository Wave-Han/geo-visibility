# Generic OpenAI-compatible chat-completions engine (Perplexity, xAI Grok).
import httpx

from .base import Engine, raise_for_status_with_body


class OpenAICompatEngine(Engine):
    def __init__(self, name: str, base_url: str, model: str, api_key: str,
                 timeout: float = 120.0, extra_body: dict | None = None):
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._extra_body = extra_body or {}

    async def ask(self, question: str) -> tuple[str, list[str]]:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": question}],
            **self._extra_body,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", json=body, headers=headers
            )
        raise_for_status_with_body(resp)
        data = resp.json()
        answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        # Perplexity returns top-level "citations"; other compat providers may not.
        citations = [c for c in (data.get("citations") or []) if isinstance(c, str)]
        return answer, citations
