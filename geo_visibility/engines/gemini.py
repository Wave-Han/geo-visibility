# Gemini engine with google_search grounding; citations come from groundingMetadata.
import httpx

from .base import Engine, raise_for_status_with_body


class GeminiEngine(Engine):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, model: str, api_key: str, timeout: float = 120.0):
        self.name = "gemini"
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    async def ask(self, question: str) -> tuple[str, list[str]]:
        url = f"{self.BASE_URL}/models/{self._model}:generateContent"
        body = {
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "tools": [{"google_search": {}}],
        }
        # key in header (not query param) so it never leaks into logged URLs
        headers = {"x-goog-api-key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
        raise_for_status_with_body(resp)
        return self._extract(resp.json())

    @staticmethod
    def _extract(data: dict) -> tuple[str, list[str]]:
        texts: list[str] = []
        citations: list[str] = []
        candidates = data.get("candidates") or [{}]
        for part in (candidates[0].get("content") or {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
        meta = candidates[0].get("groundingMetadata") or {}
        for chunk in meta.get("groundingChunks") or []:
            uri = (chunk.get("web") or {}).get("uri")
            if uri:
                citations.append(uri)
        return "\n".join(texts), citations
