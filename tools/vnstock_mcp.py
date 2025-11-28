from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
import yaml

# Try import MCP client (optional, chỉ cần nếu dùng SSE/stdio transport)
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class VnstockMCP:
    """
    Adapter để kết nối với vnstock-mcp-server.
    - Hỗ trợ nhiều transport modes: stdio, sse, streamable-http
    - Đọc cấu hình từ configs/tools.yaml
    - Có fallback mock khi chưa cấu hình
    - Tích hợp với Google ADK để agent có thể gọi MCP tools
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "configs", "tools.yaml"
        )
        self.config = self._load_config()
        self.transport = self.config.get("transport", "streamable-http")
        self.base_url = self.config.get("base_url")
        self.mount_path = self.config.get("mount_path", "/sse")
        self.timeout = self.config.get("timeout", 15.0)

        # Initialize client based on transport
        if self.transport == "streamable-http" and self.base_url:
            self._client = httpx.Client(timeout=self.timeout)
        elif self.transport in ("sse", "stdio") and MCP_AVAILABLE:
            self._client = None  # MCP client sẽ được khởi tạo khi cần
        else:
            self._client = None

    def _load_config(self) -> Dict[str, Any]:
        """Load cấu hình từ tools.yaml"""
        default_config = {
            "transport": "streamable-http",
            "base_url": None,
            "mount_path": "/sse",
            "timeout": 15.0,
        }

        if not os.path.exists(self.config_path):
            return default_config

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        mcp_config = data.get("mcp", {})

        return {
            "transport": mcp_config.get("transport", default_config["transport"]),
            "base_url": mcp_config.get("base_url"),
            "mount_path": mcp_config.get("mount_path", default_config["mount_path"]),
            "timeout": float(mcp_config.get("timeout", default_config["timeout"])),
            "stdio": mcp_config.get("stdio", {}),
            "adk": mcp_config.get("adk", {}),
        }

    def _call_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gọi MCP tool qua MCP protocol.
        - streamable-http: Dùng JSON-RPC over HTTP
        - SSE/stdio: Dùng MCP client (cần async/subprocess)
        """
        # streamable-http: Dùng JSON-RPC
        if self.transport == "streamable-http":
            return self._call_mcp_jsonrpc(
                method="tools/call",
                params={"name": tool_name, "arguments": arguments},
            )

        # SSE/stdio: Cần MCP client
        if not MCP_AVAILABLE:
            return {
                "error": "MCP client not available. Install with: uv sync --extra mcp",
                "tool": tool_name,
                "transport": self.transport,
                "note": "SSE/stdio transport requires MCP client. Or use streamable-http transport.",
            }

        if self.transport == "sse":
            if not self.base_url:
                return {
                    "error": "base_url not configured for SSE transport",
                    "tool": tool_name,
                }
            # SSE transport - cần async, sẽ implement sau nếu cần
            return {
                "error": "SSE transport requires async implementation",
                "tool": tool_name,
                "note": "Consider using streamable-http transport for sync calls",
            }

        elif self.transport == "stdio":
            # Stdio transport - cần subprocess, sẽ implement sau nếu cần
            return {
                "error": "Stdio transport requires subprocess implementation",
                "tool": tool_name,
                "note": "Consider using streamable-http transport for sync calls",
            }

        return {"error": f"Unsupported transport: {self.transport}", "tool": tool_name}

    def _call_http_tool(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Gọi tool qua HTTP REST API (streamable-http transport) - DEPRECATED, dùng _call_mcp_jsonrpc"""
        # Redirect to JSON-RPC
        return {"error": "Use MCP JSON-RPC for streamable-http transport"}

    def _call_mcp_jsonrpc(
        self, method: str, params: Optional[Dict[str, Any]] = None, request_id: int = 1
    ) -> Dict[str, Any]:
        """
        Gọi MCP tool qua JSON-RPC protocol (streamable-http transport).
        FastMCP với streamable-http dùng JSON-RPC over HTTP.
        """
        if not self._client or not self.base_url:
            return {
                "error": "HTTP client not configured",
                "method": method,
                "note": "vnstock MCP not configured. Set base_url in tools.yaml",
            }

        # JSON-RPC request payload
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id,
        }
        if params:
            payload["params"] = params

        # Thử các endpoint có thể có
        endpoints_to_try = ["/mcp", "/"]

        for endpoint in endpoints_to_try:
            try:
                url = f"{self.base_url}{endpoint}"
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                # Thêm MCP-Protocol-Version header nếu cần
                # headers["MCP-Protocol-Version"] = "2024-11-05"

                resp = self._client.post(
                    url, json=payload, headers=headers, timeout=self.timeout
                )

                if resp.status_code == 404 and endpoint != endpoints_to_try[-1]:
                    # Thử endpoint tiếp theo
                    continue

                resp.raise_for_status()
                result = resp.json()

                # Kiểm tra JSON-RPC response
                if "error" in result:
                    return {
                        "error": result["error"].get("message", "Unknown error"),
                        "code": result["error"].get("code"),
                        "method": method,
                    }

                # Trả về result nếu có
                return result.get("result", result)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and endpoint != endpoints_to_try[-1]:
                    continue
                return {
                    "error": f"HTTP {e.response.status_code}: {e.response.text}",
                    "method": method,
                    "endpoint": endpoint,
                }
            except Exception as e:
                if endpoint == endpoints_to_try[-1]:
                    # Lỗi cuối cùng, trả về
                    return {
                        "error": str(e),
                        "method": method,
                        "endpoint": endpoint,
                        "note": f"Failed to call MCP server: {e}",
                    }
                # Tiếp tục thử endpoint tiếp theo
                continue

        return {
            "error": "Could not connect to MCP server",
            "method": method,
            "base_url": self.base_url,
        }

    # ===== Public APIs - Giữ backward compatibility =====
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get stock quote - sử dụng MCP tool get_quote_history_price"""
        if self.transport == "streamable-http":
            return self._call_http_tool("/quote", {"symbol": symbol})
        else:
            # Gọi MCP tool get_quote_history_price
            return self._call_mcp_tool(
                "get_quote_history_price", {"symbol": symbol, "output_format": "json"}
            )

    def get_history(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get stock history - sử dụng MCP tool get_quote_history_price"""
        params: Dict[str, Any] = {"symbol": symbol, "output_format": "json"}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if interval:
            params["interval"] = interval

        if self.transport == "streamable-http":
            return self._call_http_tool("/history", params)
        else:
            return self._call_mcp_tool("get_quote_history_price", params)

    def get_finance(self, symbol: str, period: Optional[str] = None) -> Dict[str, Any]:
        """Get financial data - sử dụng MCP tool get_income_statements"""
        params: Dict[str, Any] = {"symbol": symbol, "output_format": "json"}
        if period:
            params["period"] = period

        if self.transport == "streamable-http":
            return self._call_http_tool("/finance", params)
        else:
            # Có thể dùng get_income_statements, get_balance_sheets, hoặc get_cash_flows
            return self._call_mcp_tool("get_income_statements", params)

    # ===== MCP Tools - Direct access to MCP server tools =====
    def call_mcp_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Gọi trực tiếp MCP tool từ vnstock-mcp-server.
        Tool names: get_company_overview, get_quote_history_price, get_income_statements, etc.

        Available MCP tools từ vnstock-mcp-server:
        - Company: get_company_overview, get_company_news, get_company_events,
          get_company_shareholders, get_company_officers, get_company_subsidiaries,
          get_company_reports, get_company_dividends, get_company_insider_deals,
          get_company_ratio_summary, get_company_trading_stats
        - Quote: get_quote_history_price, get_quote_intraday_price, get_quote_price_depth
        - Finance: get_income_statements, get_balance_sheets, get_cash_flows,
          get_finance_ratios, get_raw_report
        - Fund: list_all_funds, search_fund, get_fund_nav_report, get_fund_top_holding,
          get_fund_industry_holding, get_fund_asset_holding
        - Trading: get_price_board
        - Misc: get_gold_price, get_exchange_rate
        - Listing: get_all_symbol_groups, get_all_industries, get_all_symbols_by_group,
          get_all_symbols_by_industry, get_all_symbols
        """
        # streamable-http không cần MCP client (dùng JSON-RPC)
        # SSE/stdio cần MCP client nhưng chưa implement
        if self.transport in ("sse", "stdio") and not MCP_AVAILABLE:
            return {
                "error": "MCP client required for SSE/stdio transport",
                "tool": tool_name,
                "note": "Install MCP client: uv sync --extra mcp, or use streamable-http transport",
                "transport": self.transport,
            }

        # Gọi MCP tool (streamable-http dùng JSON-RPC, không cần MCP client)
        return self._call_mcp_tool(tool_name, kwargs)

    def list_available_tools(self) -> Dict[str, Any]:
        """
        Liệt kê tất cả MCP tools có sẵn từ vnstock-mcp-server.
        Hữu ích để Google ADK agent biết các tools có thể gọi.
        """
        # Danh sách tools từ vnstock-mcp-server (hardcoded từ server.py)
        tools = {
            "company": [
                "get_company_overview",
                "get_company_news",
                "get_company_events",
                "get_company_shareholders",
                "get_company_officers",
                "get_company_subsidiaries",
                "get_company_reports",
                "get_company_dividends",
                "get_company_insider_deals",
                "get_company_ratio_summary",
                "get_company_trading_stats",
            ],
            "quote": [
                "get_quote_history_price",
                "get_quote_intraday_price",
                "get_quote_price_depth",
            ],
            "finance": [
                "get_income_statements",
                "get_balance_sheets",
                "get_cash_flows",
                "get_finance_ratios",
                "get_raw_report",
            ],
            "fund": [
                "list_all_funds",
                "search_fund",
                "get_fund_nav_report",
                "get_fund_top_holding",
                "get_fund_industry_holding",
                "get_fund_asset_holding",
            ],
            "trading": [
                "get_price_board",
            ],
            "misc": [
                "get_gold_price",
                "get_exchange_rate",
            ],
            "listing": [
                "get_all_symbol_groups",
                "get_all_industries",
                "get_all_symbols_by_group",
                "get_all_symbols_by_industry",
                "get_all_symbols",
            ],
        }

        return {
            "transport": self.transport,
            "base_url": self.base_url,
            "configured": self.base_url is not None,
            "tools": tools,
            "total_tools": sum(len(v) for v in tools.values()),
            "note": "Use call_mcp_tool(tool_name, **kwargs) to call any of these tools",
        }
