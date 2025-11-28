"""Chat endpoint for chatbot API."""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..deps import get_agent
from ...schemas.chat import ChatRequest, ChatResponse, SuggestionMessage
from ...schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenNewsInstruction,
    OpenStockDetailInstruction,
    FeatureInstruction,
    BuyStockData,
    BuyFlowStep,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _extract_intent_from_reply(reply: str, agent_output: dict) -> str:
    """Extract intent from agent reply or output."""
    # Kiểm tra agent_output trước
    if isinstance(agent_output, dict):
        intent = agent_output.get("intent")
        if intent:
            return intent

    # Nếu không có intent trong output, thử parse từ reply
    reply_lower = reply.lower()
    if (
        "tổng quan" in reply_lower
        or "market overview" in reply_lower
        or "thị trường" in reply_lower
    ):
        return "show_market_overview"
    elif "mua" in reply_lower or "buy" in reply_lower:
        return "buy_stock"
    elif "tin tức" in reply_lower or "news" in reply_lower:
        return "view_news"
    elif (
        "chi tiết" in reply_lower
        or "detail" in reply_lower
        or "thông tin" in reply_lower
    ):
        return "stock_detail"

    return None


def _build_ui_effects(
    intent: str, agent_output: dict, reply: str
) -> list[FeatureInstruction]:
    """Build UI effects from agent intent and output."""
    ui_effects: list[FeatureInstruction] = []

    if intent == "show_market_overview":
        ui_effects.append(ShowMarketOverviewInstruction())

    elif intent == "buy_stock":
        symbol = agent_output.get("symbol") or _extract_symbol_from_reply(reply)
        price = agent_output.get("price") or agent_output.get("currentPrice")

        if symbol and price:
            steps = agent_output.get(
                "steps",
                [
                    {"id": "choose_volume", "title": "Chọn khối lượng"},
                    {"id": "choose_price", "title": "Chọn giá đặt lệnh"},
                    {"id": "confirm", "title": "Xác nhận lệnh"},
                ],
            )

            step_models = [
                BuyFlowStep(**s) if isinstance(s, dict) else s for s in steps
            ]

            ui_effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=float(price),
                        steps=step_models,
                    )
                )
            )

    elif intent == "view_news":
        news_data = agent_output.get("news_data")
        if news_data:
            ui_effects.append(OpenNewsInstruction(payload=news_data))

    elif intent == "stock_detail":
        stock_detail = agent_output.get("stock_detail")
        if stock_detail:
            ui_effects.append(OpenStockDetailInstruction(payload=stock_detail))

    return ui_effects


def _extract_symbol_from_reply(reply: str) -> Optional[str]:
    """Extract stock symbol from reply text."""
    import re

    # Tìm mã chứng khoán (thường là 3-4 chữ cái in hoa)
    matches = re.findall(r"\b([A-Z]{3,4})\b", reply)
    if matches:
        return matches[0]
    return None


def _parse_ui_effects_from_reply(reply: str, query: str) -> list[FeatureInstruction]:
    """
    Parse agent reply để detect UI effects cần thiết
    
    Logic:
    - Nếu reply có số liệu giá → có thể show chart
    - Nếu reply có bảng dữ liệu → table
    - Nếu có so sánh nhiều mã → comparison
    """
    effects = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # Phát hiện nhu cầu xem tổng quan thị trường
    if any(
        kw in query_lower or kw in reply_lower
        for kw in ["tổng quan", "market overview", "thị trường chung"]
    ):
        effects.append(ShowMarketOverviewInstruction())

    # Phát hiện ý định mua cổ phiếu
    if any(kw in query_lower for kw in ["mua", "buy", "đặt lệnh"]):
        symbol = _extract_symbol_from_reply(reply) or _extract_symbol_from_reply(query)
        if symbol:
            # Hướng dẫn mua đơn giản - giá thực sẽ lấy từ agent
            effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=0.0,  # Placeholder, should be filled by agent
                        steps=[
                            BuyFlowStep(id="choose_volume", title="Chọn khối lượng"),
                            BuyFlowStep(
                                id="choose_price", title="Chọn giá đặt lệnh"
                            ),
                            BuyFlowStep(id="confirm", title="Xác nhận lệnh"),
                        ],
                    )
                )
            )

    # Phát hiện yêu cầu xem tin tức
    if any(kw in query_lower or kw in reply_lower for kw in ["tin tức", "news", "sự kiện"]):
        # Cần trích xuất dữ liệu tin tức từ agent
        pass

    # Phát hiện yêu cầu xem chi tiết cổ phiếu
    symbol = _extract_symbol_from_reply(query)
    if symbol and any(
        kw in query_lower for kw in ["chi tiết", "detail", "thông tin", "báo cáo"]
    ):
        effects.append(OpenStockDetailInstruction(payload={"symbol": symbol}))

    return effects


def _generate_suggestions(reply: str, query: str) -> list[SuggestionMessage]:
    """
    Generate suggestion messages dựa trên reply và query
    
    Logic:
    - Nếu reply về giá → suggest xem lịch sử
    - Nếu reply về 1 mã → suggest so sánh
    - Luôn suggest câu hỏi tương tự
    """
    import re

    suggestions = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # Gợi ý dữ liệu lịch sử nếu nói về giá hiện tại
    if any(kw in reply_lower for kw in ["giá hiện tại", "giá hôm nay", "current price"]):
        suggestions.append(
            SuggestionMessage(
                text="Xem lịch sử giá 1 tháng qua",
                action="query:lịch sử giá",
                icon="📊",
            )
        )

    # Gợi ý so sánh nếu chỉ nhắc 1 cổ phiếu
    symbols = re.findall(r"\b([A-Z]{3,4})\b", query)
    if len(symbols) == 1:
        suggestions.append(
            SuggestionMessage(
                text=f"So sánh {symbols[0]} với mã khác",
                action=f"query:so sánh {symbols[0]}",
                icon="🔍",
            )
        )

    # Gợi ý thông tin tài chính nếu hỏi về giá
    if any(kw in query_lower for kw in ["giá", "price"]):
        suggestions.append(
            SuggestionMessage(
                text="Xem báo cáo tài chính",
                action="query:báo cáo tài chính",
                icon="📈",
            )
        )

    # Gợi ý mua nếu nói về giá
    if any(kw in reply_lower for kw in ["giá", "price"]) and "mua" not in query_lower:
        symbol = _extract_symbol_from_reply(query)
        if symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Mua {symbol}",
                    action=f"buy:{symbol}",
                    icon="💰",
                )
            )

    # Luôn gợi ý trợ giúp
    if not suggestions:
        suggestions.append(
            SuggestionMessage(
                text="Tôi có thể hỏi gì khác?", action="help", icon="❓"
            )
        )

    return suggestions[:3]  # Max 3 suggestions


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    agent=Depends(get_agent),
):
    """
    Nhận messages từ web, gọi ADK agent, trả text + ui_effects + suggestions.
    
    Flow:
    1. Extract user message
    2. Run agent
    3. Parse UI effects từ reply
    4. Generate suggestions
    5. Return ChatResponse
    """
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    # Lấy user message cuối cùng
    user_message = payload.messages[-1].content

    # Build conversation history cho agent
    # LlmAgent có thể nhận messages dưới dạng list hoặc string
    conversation_history = []
    for msg in payload.messages:
        if msg.role == "system":
            # System message có thể được set qua instruction của agent
            pass
        elif msg.role == "user":
            conversation_history.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            conversation_history.append({"role": "assistant", "content": msg.content})

    # Run agent
    agent_result = await _run_agent(
        agent, user_message, conversation_history, payload.meta
    )

    reply_text = agent_result.get("reply", "")

    # Import services để parse UI và generate suggestions
    from ...services import parse_ui_effects, extract_intent, generate_suggestions

    # Parse UI effects
    ui_effects = parse_ui_effects(reply_text, user_message)

    # Extract intent và generate suggestions
    intent = extract_intent(reply_text, user_message)
    suggestions = generate_suggestions(reply_text, user_message, intent)

    return ChatResponse(
        reply=reply_text,
        ui_effects=ui_effects,
        suggestion_messages=suggestions,
        raw_agent_output=agent_result,
    )


APP_NAME = "vnstock_app"
SESSION_SERVICE = InMemorySessionService()


async def _ensure_session(user_id: str, session_id: str):
    """
    Đảm bảo session tồn tại trong InMemorySessionService. Nếu chưa có thì tạo.
    """
    session = await SESSION_SERVICE.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        session = await SESSION_SERVICE.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    return session


def _create_runner(agent) -> Runner:
    return Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
    )


def _run_blocking(agent, user_id: str, session_id: str, user_message: str):
    runner = _create_runner(agent)

    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)],
    )

    reply_text = ""
    events_dump = []

    for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Parse event text từ nhiều cấu trúc khác nhau
        event_text = None
        
        # Thử 1: event.content.parts[0].text (định dạng ADK chuẩn)
        if hasattr(event, "content") and event.content is not None:
            if hasattr(event.content, "parts") and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        event_text = part.text
                        break
        
        # Thử 2: event.text (simple format)
        if not event_text and hasattr(event, "text") and event.text:
            event_text = event.text
        
        # Thử 3: event.message (một số phiên bản ADK)
        if not event_text and hasattr(event, "message") and event.message:
            if isinstance(event.message, str):
                event_text = event.message
            elif hasattr(event.message, "text"):
                event_text = event.message.text
        
        # Thử 4: Kiểm tra xem event có phải là Content type không
        if not event_text:
            try:
                # Đôi khi event CHÍNH LÀ Content object
                if hasattr(event, "parts") and event.parts:
                    for part in event.parts:
                        if hasattr(part, "text") and part.text:
                            event_text = part.text
                            break
            except Exception:
                pass

        # Lưu thông tin event để debug
        try:
            event_info = {
                "author": getattr(event, "author", None),
                "has_is_final": hasattr(event, "is_final_response"),
                "text": event_text,
                "type": type(event).__name__,
            }
            events_dump.append(event_info)
        except Exception:
            pass

        # Cập nhật reply với text mới nhất
        if event_text:
            reply_text = event_text

    return reply_text, events_dump


async def _run_agent(
    agent, user_message: str, history: List[Dict[str, str]], meta=None
) -> Dict[str, Any]:
    user_id = getattr(meta, "user_id", "user-unknown") if meta else "user-unknown"
    raw_session_id = getattr(meta, "session_id", None) if meta else None
    session_id = raw_session_id or "default-session"

    try:
        await _ensure_session(user_id=user_id, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot create/get session: {e}")

    try:
        reply_text, events_dump = await asyncio.to_thread(
            _run_blocking,
            agent,
            user_id,
            session_id,
            user_message,
        )
    except Exception as e:
        # Log error nhưng không crash - trả về error message
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Agent runner failed: {e}")
        print(f"[ERROR] Traceback: {error_trace}")
        
        # Return friendly error message thay vì HTTP 500
        reply_text = f"Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại."
        events_dump = [{
            "error": str(e),
            "error_type": type(e).__name__,
        }]

    if not reply_text:
        reply_text = "[DEBUG] Agent không trả về text – kiểm tra raw_agent_output.events để debug."

    return {
        "reply": reply_text,
        "events": events_dump,
    }
