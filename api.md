Hiểu câu hỏi của bạn là:
“OK, FastAPI đứng giữa rồi, **API của app nên thiết kế những endpoint nào, path ra sao, body/response như thế nào?**”

Mình gợi ý một **structure API tối giản nhưng đủ xài cho MVP** như sau.

---

## 1. Tổng quan structure API

Base URL:

* `BASE_URL = /api`
* `V1 = /api/v1`

Các endpoint chính:

1. `GET  /health` – check server sống.
2. `POST /api/v1/chat` – endpoint chính cho chatbot.

MVP thực ra chỉ cần **2 cái**:

* `GET /health`
* `POST /api/v1/chat`

---

## 2. Chi tiết từng API

### 2.1. `GET /health`

Dùng để:

* Dev/test nhanh server có chạy không.
* K8s / Docker health check.

**Request**

* Method: `GET`
* URL: `/health`
* Body: none

**Response 200**

```json
{
  "status": "ok"
}
```

---

### 2.2. `POST /api/v1/chat` – API chính cho chatbot

Đây là nơi **frontend gửi text + history**, backend gọi **ADK Agent**, rồi trả về:

* `reply`: câu trả lời assistant (cho panel bên phải)
* `ui_effects`: list `FeatureInstruction` (cho panel bên trái)

#### URL + Method

* Method: `POST`
* URL: `/api/v1/chat`

#### Request body

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a trading assistant..."
    },
    {
      "role": "user",
      "content": "Cho mình xem tổng quan thị trường hôm nay"
    }
  ],
  "meta": {
    "user_id": "user-123",
    "session_id": "sess-abc",
    "locale": "vi-VN"
  }
}
```

Schema (đã define trong `app/schemas/chat.py`):

```python
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
```

#### Response body

Ví dụ 1 – Mở **Market Overview**:

```json
{
  "reply": "Đây là tổng quan thị trường hôm nay, mình đã mở panel Market Overview cho bạn ở bên trái.",
  "ui_effects": [
    {
      "type": "SHOW_MARKET_OVERVIEW"
    }
  ],
  "raw_agent_output": {
    "intent": "show_market_overview",
    "indices": [/* ... */]
  }
}
```

Ví dụ 2 – Mở flow **mua cổ phiếu MWG**:

```json
{
  "reply": "Mình mở flow mua cổ phiếu MWG cho bạn nhé.",
  "ui_effects": [
    {
      "type": "OPEN_BUY_STOCK",
      "payload": {
        "symbol": "MWG",
        "currentPrice": 81400,
        "steps": [
          { "id": "choose_volume", "title": "Chọn khối lượng" },
          { "id": "choose_price", "title": "Chọn giá đặt lệnh" },
          { "id": "confirm", "title": "Xác nhận lệnh" }
        ]
      }
    }
  ],
  "raw_agent_output": {
    "intent": "buy_stock",
    "symbol": "MWG",
    "price": 81400
  }
}
```

Schema (đã define trong `app/schemas/chat.py`):

```python
class ChatResponse(BaseModel):
    reply: str
    ui_effects: List[FeatureInstruction] = []
    raw_agent_output: Optional[dict] = None
```

---

## 3. Optional: Session API (nếu sau này muốn quản lý phiên chat)

Không bắt buộc cho MVP, nhưng nếu bạn muốn server **tự giữ history** thay vì client gửi full `messages` mỗi lần, có thể thêm:

### 3.1. `POST /api/v1/sessions`

Tạo session mới:

**Request**

```json
{
  "user_id": "user-123",
  "agent_id": "vnstock-default"
}
```

**Response**

```json
{
  "session_id": "sess-abc",
  "created_at": "2025-11-21T06:00:00Z"
}
```

### 3.2. `GET /api/v1/sessions/{session_id}`

Lấy lại history:

```json
{
  "session_id": "sess-abc",
  "messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

Khi đó `POST /api/v1/chat` có thể rút gọn lại:

```json
{
  "session_id": "sess-abc",
  "message": {
    "role": "user",
    "content": "Cho mình xem tổng quan thị trường hôm nay"
  }
}
```

---

## 4. Tóm tắt “API structure của app”

Nếu viết ngắn gọn kiểu spec:

```text
GET  /health
  - 200: { status: "ok" }

POST /api/v1/chat
  - body: {
      messages: ChatMessage[],
      meta?: { user_id?, session_id?, locale? }
    }
  - 200: {
      reply: string,
      ui_effects: FeatureInstruction[],
      raw_agent_output?: object
    }

