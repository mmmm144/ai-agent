"""Chat request and response schemas."""

import re
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from .ui import FeatureInstruction


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatMetadata(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    locale: Optional[str] = "vi-VN"


class ChatRequest(BaseModel):
    """
    Chat request với message history và validation tiếng Việt
    """

    messages: List[ChatMessage]
    meta: Optional[ChatMetadata] = None

    @field_validator("messages")
    @classmethod
    def validate_vietnamese_messages(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        """Validate và normalize message content (tiếng Việt)"""
        if not v:
            raise ValueError("Messages không được rỗng")

        # Validate tin nhắn người dùng cuối cùng
        last_user_msg = None
        for msg in reversed(v):
            if msg.role == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            raise ValueError("Phải có ít nhất 1 message từ user")

        # Normalize và validate content
        content = last_user_msg.content.strip()
        if not content:
            raise ValueError("Message content không được rỗng")

        # Normalize whitespace
        content = re.sub(r"\s+", " ", content)

        # Check có chữ cái (accept cả tiếng Việt có dấu và không dấu)
        # Pattern bao gồm: a-z, A-Z, và tất cả Vietnamese diacritics
        has_letters = re.search(
            r"[a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ]",
            content
        )
        
        if not has_letters:
            raise ValueError(
                "Message phải chứa ít nhất một chữ cái (có dấu hoặc không dấu đều được)"
            )

        # Tùy chọn: Kiểm tra nội dung có quá nhiều ký tự đặc biệt không (phát hiện spam)
        # Đếm tỷ lệ chữ cái so với ký tự đặc biệt
        letter_count = len(re.findall(
            r"[a-zA-ZàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ]",
            content
        ))
        total_chars = len(content.replace(" ", ""))
        
        if total_chars > 0 and letter_count / total_chars < 0.3:
            raise ValueError(
                "Message có quá nhiều ký tự đặc biệt. Vui lòng nhập nội dung rõ ràng hơn."
            )

        # Cập nhật nội dung đã chuẩn hóa
        last_user_msg.content = content

        return v


class SuggestionMessage(BaseModel):
    """Gợi ý câu hỏi/action tiếp theo cho user"""

    text: str = Field(..., description="Nội dung gợi ý")
    action: Optional[str] = Field(
        None, description="Action để thực hiện (VD: 'query:lịch sử giá')"
    )
    icon: Optional[str] = Field(None, description="Icon emoji (VD: '📊', '🔍')")


class ChatResponse(BaseModel):
    """
    Chat response với UI effects và suggestions
    
    Example:
        {
            "reply": "Giá VCB hôm nay là 95,000 VNĐ...",
            "ui_effects": [
                {
                    "feature": "chart",
                    "description": "Hiển thị biểu đồ giá VCB",
                    "parameters": {"symbol": "VCB", "period": "1M"}
                }
            ],
            "suggestion_messages": [
                {
                    "text": "Xem lịch sử giá 1 tháng qua",
                    "action": "query:lịch sử giá VCB",
                    "icon": "📊"
                }
            ],
            "raw_agent_output": {
                "model": "gemini-2.5-flash",
                "tokens": 150
            }
        }
    """

    reply: str = Field(..., description="Câu trả lời từ agent")
    ui_effects: List[FeatureInstruction] = Field(
        default=[], description="Danh sách UI components cần render"
    )
    suggestion_messages: List[SuggestionMessage] = Field(
        default=[], description="Danh sách gợi ý câu hỏi tiếp theo"
    )
    raw_agent_output: Optional[dict] = Field(
        None, description="Raw output từ agent (debug)"
    )
