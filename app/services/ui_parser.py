"""
Service để parse agent reply và generate UI effects
"""

import re
from typing import Optional

from ..schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenStockDetailInstruction,
    FeatureInstruction,
    BuyStockData,
    BuyFlowStep,
)


def extract_symbol_from_text(text: str) -> Optional[str]:
    """
    Extract stock symbol từ text (3-4 chữ cái in hoa)
    
    Args:
        text: Text chứa mã cổ phiếu
        
    Returns:
        Stock symbol hoặc None
        
    Example:
        >>> extract_symbol_from_text("Giá VCB hôm nay")
        "VCB"
    """
    matches = re.findall(r"\b([A-Z]{3,4})\b", text)
    return matches[0] if matches else None


def parse_ui_effects(reply: str, query: str) -> list[FeatureInstruction]:
    """
    Parse agent reply để detect UI effects cần thiết
    
    Args:
        reply: Agent reply text
        query: User query text
        
    Returns:
        List of UI effect instructions
        
    Logic:
    - "tổng quan thị trường" → ShowMarketOverviewInstruction
    - "mua cổ phiếu" → OpenBuyStockInstruction
    - "chi tiết cổ phiếu" → OpenStockDetailInstruction
    """
    effects = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # 1. Market overview
    market_keywords = ["tổng quan", "market overview", "thị trường chung", "vnindex"]
    if any(kw in query_lower or kw in reply_lower for kw in market_keywords):
        effects.append(ShowMarketOverviewInstruction())

    # 2. Buy stock
    buy_keywords = ["mua", "buy", "đặt lệnh", "order"]
    if any(kw in query_lower for kw in buy_keywords):
        symbol = extract_symbol_from_text(reply) or extract_symbol_from_text(query)
        if symbol:
            effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=0.0,  # Agent should provide this
                        steps=[
                            BuyFlowStep(id="choose_volume", title="Chọn khối lượng"),
                            BuyFlowStep(id="choose_price", title="Chọn giá đặt lệnh"),
                            BuyFlowStep(id="confirm", title="Xác nhận lệnh"),
                        ],
                    )
                )
            )

    # 3. Stock detail
    detail_keywords = ["chi tiết", "detail", "thông tin", "báo cáo", "phân tích"]
    symbol = extract_symbol_from_text(query)
    if symbol and any(kw in query_lower for kw in detail_keywords):
        effects.append(OpenStockDetailInstruction(payload={"symbol": symbol}))

    return effects


def extract_intent(reply: str, query: str) -> Optional[str]:
    """
    Extract user intent từ query/reply
    
    Returns:
        Intent string: "market_overview", "buy_stock", "stock_detail", "price_query", None
    """
    query_lower = query.lower()
    reply_lower = reply.lower()

    # Market overview
    if any(kw in query_lower for kw in ["tổng quan", "market overview", "vnindex"]):
        return "market_overview"

    # Buy stock
    if any(kw in query_lower for kw in ["mua", "buy", "đặt lệnh"]):
        return "buy_stock"

    # Stock detail
    if any(kw in query_lower for kw in ["chi tiết", "detail", "thông tin chi tiết"]):
        return "stock_detail"

    # Price query
    if any(kw in query_lower for kw in ["giá", "price"]):
        return "price_query"

    return None
