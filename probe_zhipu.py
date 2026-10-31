# One-shot probe: does the zhipu engine actually run web_search?
# Run with ZHIPU_API_KEY set:   python probe_zhipu.py
# Optionally override model:   $env:ZHIPU_MODEL="glm-4.6"; python probe_zhipu.py
# If the answer is dated (e.g. "as of 2023") or message has no web_search /
# tool_calls field, the model answered from memory and cannot be used as a
# search-grounded measurement engine.
import asyncio
import json
import os

import httpx

KEY = os.environ.get("ZHIPU_API_KEY", "")
assert KEY, "set ZHIPU_API_KEY first"

BODY = {
    "model": os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
    "messages": [{"role": "user",
                  "content": "What are the best robot vacuums right now? "
                             "Name the current flagship models."}],
    "tools": [{"type": "web_search",
               "web_search": {"enable": True, "search_result": True}}],
}


async def main() -> None:
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            json=BODY,
            headers={"Authorization": f"Bearer {KEY}"},
        )
    print("status:", resp.status_code)
    if resp.status_code != 200:
        print(resp.text[:300])
        return
    msg = resp.json().get("choices", [{}])[0].get("message", {})
    print("message keys:", list(msg.keys()))
    print("--- answer head ---")
    print((msg.get("content") or "")[:500])
    for k in ("web_search", "tool_calls"):
        if k in msg:
            print(f"--- {k} ---")
            print(json.dumps(msg[k], ensure_ascii=False)[:800])


asyncio.run(main())
