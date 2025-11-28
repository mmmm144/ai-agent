from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi gốc của user")
    symbol: Optional[str] = Field(None, description="Mã CK như VNM, FPT")
    # optional filters for history/finance
    start_date: Optional[str] = None  # yyyy-mm-dd
    end_date: Optional[str] = None
    interval: Optional[str] = None  # 1d, 1h, 1m, ...
    period: Optional[str] = None  # quarterly, yearly, trailing-12m, ...
    intent: Optional[str] = None  # override if đã biết


class StandardResponse(BaseModel):
    ok: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[str] = None
    error: Optional[str] = None
