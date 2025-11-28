You already have 2 pieces solved:

* **Frontend contract + UI flow** (FeatureInstruction, 2-side layout, etc.) 
* **Python “Agent Development Kit” project** with `agents/`, `tools/`, configs, etc. 

Now we just need to put a **FastAPI layer in the middle** so:

> Website ⟷ FastAPI (chatbot backend) ⟷ ADK Agent ⟷ MCP tools

Below is a concrete structure + example code you can copy/paste and adapt.

---

## 1. Target architecture (end-to-end)

**Flow:**

1. Website gửi request `POST /api/chat` với:

   * `messages`: lịch sử chat
   * `meta`: userId, sessionId, v.v.
2. FastAPI nhận → gọi `root_agent` trong `agents/` để xử lý. 
3. Agent chạy tool MCP (vnstock, v.v.) → trả về:

   * `reply`: text hiển thị bên phải (chat panel)
   * `ui_effects`: mảng `FeatureInstruction[]` để frontend render left side (market, buy stock, news…) 
4. FastAPI trả JSON này về website → website update:

   * Right side: thêm assistant message
   * Left side: apply `ui_effects` vào `FeatureState` (giống bạn đã thiết kế).

---

## 2. Folder structure cho FastAPI + ADK

Giữ nguyên cấu trúc ADK hiện tại, chỉ **thêm layer `app/` cho FastAPI**: 

```bash
test-adk/
├── agents/
│   ├── __init__.py          # export root_agent, create_vnstock_agent
│   └── vnstock_agent.py
│
├── tools/
│   ├── __init__.py
│   ├── mcp_client.py
│   ├── company_tools.py
│   ├── quote_tools.py
│   ├── finance_tools.py
│   ├── fund_tools.py
│   ├── listing_tools.py
│   ├── trading_tools.py
│   └── misc_tools.py
│
├── configs/
│   ├── mcp_config.yaml
│   └── agent_config.yaml
│
├── app/                     # 🔹 FastAPI layer (mới thêm)
│   ├── __init__.py
│   ├── main.py              # FastAPI app, uvicorn entry
│   ├── core/
│   │   ├── config.py        # CORS, settings, etc.
│   │   └── logging.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py          # common dependencies (get_agent, etc.)
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── chat.py      # /api/v1/chat endpoint
│   └── schemas/
│       ├── chat.py          # Pydantic models for ChatRequest/Response
│       └── ui.py            # Pydantic models for FeatureInstruction
│
├── main.py                  # (optional) CLI entry cũ
├── pyproject.toml
├── README.md
└── STRUCTURE.md
```

Frontend Next.js/React của bạn (cấu trúc `features/`, `FeatureArea`, Chatbot panel…) **không cần đổi**, chỉ cần align JSON contract với FastAPI. 

---

## 3. JSON contract giữa Web ⟷ FastAPI

### 3.1. Pydantic models: UI Instructions (match frontend `FeatureInstruction`)

`app/schemas/ui.py`:

```python
from typing import List, Literal, Optional
from pydantic import BaseModel


class BuyFlowStep(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class MarketOverviewData(BaseModel):
    # tạm đơn giản, bạn có thể align đúng với TS type front-end
    indices: list[dict] = []
    mainChart: dict = {}
    trendingStocks: list[dict] = []


class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    timeAgo: str
    sentiment: Literal["positive", "negative", "neutral"]


class NewsData(BaseModel):
    symbol: Optional[str] = None
    items: list[NewsItem]


class StockDetailData(BaseModel):
    symbol: str
    name: str
    description: Optional[str] = None
    price: float
    changePercent: float
    intradayChart: list[dict]


class BuyStockData(BaseModel):
    symbol: str
    currentPrice: float
    steps: list[BuyFlowStep]
    # front-end sẽ set currentStepIndex = 0 khi nhận data
```

`FeatureInstruction` (y chang frontend `FeatureInstruction` type): 

```python
class ShowMarketOverviewInstruction(BaseModel):
    type: Literal["SHOW_MARKET_OVERVIEW"] = "SHOW_MARKET_OVERVIEW"


class OpenBuyStockInstruction(BaseModel):
    type: Literal["OPEN_BUY_STOCK"] = "OPEN_BUY_STOCK"
    payload: BuyStockData


class OpenNewsInstruction(BaseModel):
    type: Literal["OPEN_NEWS"] = "OPEN_NEWS"
    payload: NewsData


class OpenStockDetailInstruction(BaseModel):
    type: Literal["OPEN_STOCK_DETAIL"] = "OPEN_STOCK_DETAIL"
    payload: StockDetailData


FeatureInstruction = (
    ShowMarketOverviewInstruction
    | OpenBuyStockInstruction
    | OpenNewsInstruction
    | OpenStockDetailInstruction
)
```

### 3.2. Chat models

`app/schemas/chat.py`:

```python
from typing import List, Optional, Literal
from pydantic import BaseModel
from .ui import FeatureInstruction


class ChatRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatMetadata(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    locale: Optional[str] = "vi-VN"


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    meta: Optional[ChatMetadata] = None


class ChatResponse(BaseModel):
    reply: str                          # text cho chatbot panel
    ui_effects: List[FeatureInstruction] = []  # mảng FeatureInstruction
    raw_agent_output: Optional[dict] = None    # optional debug
```

---

## 4. FastAPI app + router

### 4.1. `app/core/config.py`

```python
from pydantic import BaseSettings


class Settings(BaseSettings):
    API_PREFIX: str = "/api"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Trading Chatbot ADK Backend"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]  # chỉnh lại domain thật

    class Config:
        env_file = ".env"


settings = Settings()
```

### 4.2. `app/api/deps.py` – dependency để lấy agent

```python
from agents import root_agent  # từ STRUCTURE.md :contentReference[oaicite:7]{index=7}


async def get_agent():
    # Nếu sau này bạn muốn multi-tenant, có thể tạo agent khác nhau ở đây
    return root_agent
```

### 4.3. `app/api/v1/chat.py` – main endpoint `/api/v1/chat`

```python
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_agent
from ...schemas.chat import ChatRequest, ChatResponse
from ...schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenNewsInstruction,
    OpenStockDetailInstruction,
    FeatureInstruction,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    agent = Depends(get_agent),
):
    """
    Nhận messages từ web, gọi ADK agent, trả text + ui_effects.
    """
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    user_message = payload.messages[-1].content

    # 1. Gọi agent (tùy bạn define API cho vnstock_agent)
    #
    # Giả sử root_agent có method async run_text() trả về string
    #
    try:
        agent_result = await agent.run(user_message)  # pseudo-code
    except Exception as e:
        # TODO: log error
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Mapping từ agent_result → reply + ui_effects
    # Ở đây minh họa: agent_result là dict:
    # {
    #   "reply": "Mình mở flow mua MWG cho bạn",
    #   "intent": "buy_stock",
    #   "symbol": "MWG",
    #   "price": 81400,
    #   ...
    # }
    #
    reply_text: str = agent_result.get("reply", "")
    ui_effects: list[FeatureInstruction] = []

    intent = agent_result.get("intent")

    if intent == "show_market_overview":
        ui_effects.append(ShowMarketOverviewInstruction())
    elif intent == "buy_stock":
        ui_effects.append(
            OpenBuyStockInstruction(
                payload={
                    "symbol": agent_result["symbol"],
                    "currentPrice": agent_result["price"],
                    "steps": agent_result.get("steps", []),
                }
            )
        )
    elif intent == "view_news":
        ui_effects.append(
            OpenNewsInstruction(
                payload=agent_result["news_data"]
            )
        )
    elif intent == "stock_detail":
        ui_effects.append(
            OpenStockDetailInstruction(
                payload=agent_result["stock_detail"]
            )
        )

    return ChatResponse(
        reply=reply_text,
        ui_effects=ui_effects,
        raw_agent_output=agent_result,
    )
```

> **Key idea:** Agent **không cần biết UI**; nó chỉ cần trả về một JSON có `intent` + data đủ để bạn wrap thành `FeatureInstruction`. Frontend đã có `FeatureArea` để render tương ứng.

### 4.4. `app/main.py` – FastAPI entry

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.v1.chat import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

Run:

```bash
uvicorn app.main:app --reload
```

---

## 5. Kết nối với frontend (Next.js / React)

Ở phía client, bạn đã có `TradingChatPanel` + logic nhận `uiEffects` và `reduceFeatureState`.

Chỉ cần gửi request:

```ts
// pseudo-code in front-end
async function callChatbot(text: string, history: ChatMessage[]): Promise<ChatResponse> {
  const res = await fetch("http://localhost:8000/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: history.concat([{ role: "user", content: text }]),
      meta: { user_id: "u123", session_id: "s456" },
    }),
  });

  if (!res.ok) throw new Error("Chat API error");
  return res.json();
}
```

Response:

```json
{
  "reply": "Mình mở flow mua MWG cho bạn.",
  "ui_effects": [
    {
      "type": "OPEN_BUY_STOCK",
      "payload": {
        "symbol": "MWG",
        "currentPrice": 81400,
        "steps": [...]
      }
    }
  ],
  "raw_agent_output": { ... }
}
```

Rồi bạn dùng đúng logic đã có:

* Append `reply` vào `messages`.
* Gọi `onUiEffects(response.ui_effects)` để update `FeatureState` → `FeatureArea` render UI tương ứng.

---

## 6. Tóm tắt nhanh

1. **Giữ nguyên ADK** (`agents/`, `tools/`, `configs/`). 
2. Thêm `app/` chứa FastAPI:

   * `app/main.py` – app + CORS + router
   * `app/api/v1/chat.py` – `/api/v1/chat`
   * `app/schemas/{chat,ui}.py` – contract Web ⟷ Backend
3. Định nghĩa `FeatureInstruction` trong Python y chang TS, để frontend apply dễ.
4. Trong router:

   * Nhận `ChatRequest`
   * Gọi `root_agent`
   * Map `intent` + data → `ui_effects: FeatureInstruction[]`
   * Return `ChatResponse` cho web.
