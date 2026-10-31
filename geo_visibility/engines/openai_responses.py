# OpenAI Responses API engine with the web_search tool enabled.
# Parsing is defensive on purpose: the API shape evolves, adjust if needed.
import httpx

from .base import Engine, raise_for_status_with_body


class OpenAIResponsesEngine(Engine):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, name: str, model: str, api_key: str,
                 base_url: str | None = None, timeout: float = 120.0):
        self.name = name
        self._model = model
        self._api_key = api_key
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    async def ask(self, question: str) -> tuple[str, list[str]]:
        body = {
            "model": self._model,
            "tools": [{"type": "web_search"}],
            "input": question,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/responses", json=body, headers=headers)
        raise_for_status_with_body(resp)
        return self._extract(resp.json())

    @staticmethod
    def _extract(data: dict) -> tuple[str, list[str]]:
        texts: list[str] = []
        citations: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") in ("output_text", "text"):
                    texts.append(part.get("text", ""))
                    for ann in part.get("annotations", []):
                        if ann.get("type") == "url_citation":
                            url = ann.get("url") or (ann.get("url_citation") or {}).get("url")
                            if url:
                                citations.append(url)
        return "\n".join(texts), citations
