"""UI instruction schemas matching frontend FeatureInstruction types."""

from typing import List, Literal, Optional
from pydantic import BaseModel


class BuyFlowStep(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class MarketOverviewData(BaseModel):
    """Data for market overview panel."""

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
    items: List[NewsItem]


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
    steps: List[BuyFlowStep]


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


# Union type cho tất cả feature instructions
FeatureInstruction = (
    ShowMarketOverviewInstruction
    | OpenBuyStockInstruction
    | OpenNewsInstruction
    | OpenStockDetailInstruction
)
