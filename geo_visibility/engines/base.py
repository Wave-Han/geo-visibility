# Abstract engine interface: every search-augmented LLM implements ask().
import abc


class Engine(abc.ABC):
    name: str

    @abc.abstractmethod
    async def ask(self, question: str) -> tuple[str, list[str]]:
        """Ask one question, return (answer_text, citation_urls)."""


def raise_for_status_with_body(resp) -> None:
    """Raise with a response-body excerpt so logged errors show the real
    API reason (model retired / quota / auth) instead of a bare status code."""
    if resp.is_success:
        return
    body = resp.text[:200].replace("\n", " ")
    raise RuntimeError(f"HTTP {resp.status_code} from {resp.request.url.path}: {body}")
