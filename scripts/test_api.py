"""Script test các endpoint của FastAPI backend."""

import asyncio
import json
from typing import Any, Dict, List

import httpx

BASE_URL = "http://localhost:8002"
HEALTH_ENDPOINT = f"{BASE_URL}/health"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/chat"

# Các payload mẫu để kích hoạt intent phổ biến
CHAT_SAMPLES: List[Dict[str, Any]] = [
    {
        "name": "market_overview",
        "payload": {
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý chứng khoán Việt Nam.",
                },
                {
                    "role": "user",
                    "content": "Cho mình xem tổng quan thị trường hôm nay.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-market"},
        },
    },
    {
        "name": "buy_stock",
        "payload": {
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý chứng khoán Việt Nam.",
                },
                {
                    "role": "user",
                    "content": "Mình muốn mua cổ phiếu MWG, hướng dẫn giúp mình.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-buy"},
        },
    },
    {
        "name": "news",
        "payload": {
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý chứng khoán Việt Nam.",
                },
                {
                    "role": "user",
                    "content": "Có tin tức gì về VNM không?",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-news"},
        },
    },
]


async def check_health(client: httpx.AsyncClient, retries: int = 5) -> None:
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(HEALTH_ENDPOINT)
            resp.raise_for_status()
            print("✅ /health:", resp.json())
            return
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            print(f"[retry {attempt}/{retries}] /health fail: {exc}. Đợi 1s...")
            await asyncio.sleep(1)


async def test_chat_samples(client: httpx.AsyncClient) -> None:
    for sample in CHAT_SAMPLES:
        name = sample["name"]
        payload = sample["payload"]
        print(f"\n=== Test chat: {name} ===")
        resp = await client.post(CHAT_ENDPOINT, json=payload)
        print("Status:", resp.status_code)
        if resp.status_code != 200:
            print("Body:", resp.text)
            continue
        data = resp.json()
        reply = data.get("reply")
        ui_effects = data.get("ui_effects", [])
        print("Reply:", reply)
        print("UI Effects:")
        print(json.dumps(ui_effects, ensure_ascii=False, indent=2))


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await check_health(client)
        await test_chat_samples(client)


if __name__ == "__main__":
    asyncio.run(main())
