# Orchestrate engine x question runs with concurrency, retries and
# append-only JSONL persistence (resumable per engine).
import asyncio
import json
import pathlib
import re
import time

from .engines import build_engines

RETRIES = 2
CONCURRENCY = 4

# defense in depth: never persist API keys that slip into error strings
_KEY_RE = re.compile(r"(key=)[A-Za-z0-9._\-]+")


def _redact(msg: str) -> str:
    return _KEY_RE.sub(r"\1***", msg)


async def _ask_with_retry(engine, question: str) -> dict:
    for attempt in range(RETRIES + 1):
        try:
            answer, citations = await engine.ask(question)
            return {"answer": answer, "citations": citations, "error": None}
        except Exception as exc:  # noqa: BLE001 - log and retry any transport/API error
            if attempt == RETRIES:
                return {"answer": "", "citations": [], "error": _redact(str(exc))}
            await asyncio.sleep(2 ** attempt)


def _existing_qids(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    qids: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # resume skips only successful answers; errored ones re-run
            if rec.get("error"):
                continue
            qids.add(rec["qid"])
    return qids


def load_records(raw_dir: pathlib.Path) -> list[dict]:
    """Load all raw records from a raw/ directory of per-engine JSONL files."""
    records: list[dict] = []
    if not raw_dir.exists():
        return records
    for path in sorted(raw_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


async def collect(cfg: dict, out_dir: pathlib.Path, pilot: bool = False,
                  pilot_brands: list[str] | None = None) -> None:
    from .questions import build_pilot_set, build_question_set, load_brands

    engines = build_engines(cfg["engines"])
    if not engines:
        raise RuntimeError("no engine available - check API keys (see README)")
    brands = load_brands(cfg["brands"])
    questions = build_question_set(brands, cfg["questions"])
    if pilot:
        brands, questions = build_pilot_set(brands, questions, pilot_brands)
        print(f"pilot mode: brands={[b.name for b in brands]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"total questions per engine: {len(questions)}")

    sem = asyncio.Semaphore(CONCURRENCY)
    for engine in engines:
        path = out_dir / f"{engine.name}.jsonl"
        done = _existing_qids(path)
        todo = [q for q in questions if q.qid not in done]
        print(f"[{engine.name}] {len(todo)} to run ({len(done)} already done)")
        if not todo:
            continue
        with open(path, "a", encoding="utf-8") as f:
            progress = {"done": 0}
            total = len(todo)

            async def run_one(q):
                async with sem:
                    result = await _ask_with_retry(engine, q.text)
                rec = {
                    "engine": engine.name,
                    "qid": q.qid,
                    "dimension": q.dimension,
                    "brand": q.brand,
                    "question": q.text,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    **result,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                progress["done"] += 1
                flag = f" ERROR {result['error'][:80]}" if result["error"] else ""
                print(f"[{engine.name}] {progress['done']}/{total} qid={q.qid}{flag}",
                      flush=True)

            await asyncio.gather(*(run_one(q) for q in todo))

    # Run summary: volume, errors and a rough token estimate (chars/4) for
    # cost checking. Exact billing lives in provider dashboards.
    records = load_records(out_dir)
    errors = sum(1 for r in records if r.get("error"))
    chars = sum(len(r.get("answer", "")) + len(r.get("question", "")) for r in records)
    print(f"done: records={len(records)} errors={errors} est_tokens~{chars // 4}")
