# Cấu trúc Project

## Tổng quan

Project được tổ chức theo cấu trúc ADK chuẩn với các module riêng biệt cho từng chức năng.

## Cấu trúc thư mục

```
test-adk/
├── agents/              # Agent implementations
│   ├── __init__.py      # Export root_agent và create_vnstock_agent
│   └── vnstock_agent.py # VNStock agent chính với MCP tools
│
├── tools/               # Tool implementations (32 tools)
│   ├── __init__.py      # Export tất cả tool classes
│   ├── mcp_client.py    # MCP client wrapper - kết nối với MCP server
│   ├── company_tools.py # Company tools (11 tools)
│   ├── quote_tools.py   # Quote tools (3 tools)
│   ├── finance_tools.py # Finance tools (5 tools)
│   ├── fund_tools.py    # Fund tools (6 tools)
│   ├── listing_tools.py # Listing tools (5 tools)
│   ├── trading_tools.py # Trading tools (1 tool)
│   └── misc_tools.py    # Misc tools (2 tools)
│
├── configs/             # Configuration files
│   ├── mcp_config.yaml  # MCP server configuration
│   └── agent_config.yaml # Agent configuration
│
├── utils/               # Utilities (reserved for future use)
│   └── __init__.py
│
├── agent/               # DEPRECATED - Giữ lại để backward compatibility
│   ├── __init__.py
│   └── agent.py         # Old agent implementation
│
├── main.py              # Main entry point
├── pyproject.toml       # Project dependencies
├── README.md            # Documentation chính
└── STRUCTURE.md         # File này
```

## Modules

### 1. Agents Module (`agents/`)

Chứa implementation của agent chính.

#### `agents/vnstock_agent.py`

- `create_vnstock_agent()`: Factory function để tạo agent với cấu hình tùy chỉnh
- `root_agent`: Agent instance mặc định (auto-created khi import)

### 2. Tools Module (`tools/`)

Chứa các wrapper classes cho MCP tools, được nhóm theo chức năng.

#### `tools/mcp_client.py`

- `MCPClient`: Client class để giao tiếp với MCP server
- `get_mcp_client()`: Factory function để lấy global client instance
- `get_mcp_tools()`: Lấy danh sách tools từ MCP server

#### Tool Classes

Mỗi class wrapper một nhóm tools:

- `CompanyTools`: 11 tools về thông tin công ty
- `QuoteTools`: 3 tools về giá cổ phiếu
- `FinanceTools`: 5 tools về báo cáo tài chính
- `FundTools`: 6 tools về quỹ đầu tư
- `ListingTools`: 5 tools về danh sách mã chứng khoán
- `TradingTools`: 1 tool về bảng giá
- `MiscTools`: 2 tools về giá vàng và tỷ giá

### 3. Configs Module (`configs/`)

Chứa các file cấu hình YAML.

#### `configs/mcp_config.yaml`

- Cấu hình MCP server (URL, timeout, transport)
- Danh sách tất cả 32 tools

#### `configs/agent_config.yaml`

- Cấu hình agent (model, description, instruction)

## Cách sử dụng

### Sử dụng Agent (Recommended)

```python
from agents import root_agent

# Sử dụng root_agent
response = await root_agent.run("Giá VCB hôm nay?")

# Hoặc tạo agent mới với cấu hình tùy chỉnh
from agents.vnstock_agent import create_vnstock_agent

agent = create_vnstock_agent(
    model="gemini-2.5-flash",
    server_url=None  # Sẽ đọc từ configs/mcp_config.yaml
)
```

### Sử dụng Tools trực tiếp

```python
from tools.company_tools import CompanyTools

company = CompanyTools()
overview = company.get_company_overview("VCB", output_format="json")
```

### Sử dụng MCP Client trực tiếp

```python
from tools.mcp_client import get_mcp_client

client = get_mcp_client()
result = client.call_tool("get_company_overview", symbol="VCB")
```

## Tools List (32 tools)

### Company Tools (11)

1. `get_company_overview`
2. `get_company_news`
3. `get_company_events`
4. `get_company_shareholders`
5. `get_company_officers`
6. `get_company_subsidiaries`
7. `get_company_reports`
8. `get_company_dividends`
9. `get_company_insider_deals`
10. `get_company_ratio_summary`
11. `get_company_trading_stats`

### Quote Tools (3)

1. `get_quote_history_price`
2. `get_quote_intraday_price`
3. `get_quote_price_depth`

### Finance Tools (5)

1. `get_income_statements`
2. `get_balance_sheets`
3. `get_cash_flows`
4. `get_finance_ratios`
5. `get_raw_report`

### Fund Tools (6)

1. `list_all_funds`
2. `search_fund`
3. `get_fund_nav_report`
4. `get_fund_top_holding`
5. `get_fund_industry_holding`
6. `get_fund_asset_holding`

### Listing Tools (5)

1. `get_all_symbol_groups`
2. `get_all_industries`
3. `get_all_symbols_by_group`
4. `get_all_symbols_by_industry`
5. `get_all_symbols`

### Trading Tools (1)

1. `get_price_board`

### Misc Tools (2)

1. `get_gold_price`
2. `get_exchange_rate`

## Best Practices

1. **Sử dụng Agent thay vì tools trực tiếp**: Agent tự động quản lý tools và context
2. **Sử dụng config files**: Thay đổi cấu hình qua YAML files thay vì hardcode
3. **Error handling**: Luôn handle exceptions khi gọi tools
4. **Caching**: MCP client tự động cache tools list để tối ưu performance

## Migration từ code cũ

Nếu đang sử dụng `agent/agent.py`:

```python
# Cũ
from agent.agent import root_agent

# Mới (Recommended)
from agents import root_agent
```

File `agent/agent.py` vẫn hoạt động nhưng đã deprecated và sẽ bị remove trong tương lai.

## Troubleshooting

### Import errors

- Đảm bảo đang chạy từ root directory của project
- Kiểm tra `sys.path` nếu có vấn đề với relative imports

### MCP connection errors

- Kiểm tra MCP server đang chạy: `curl <URL từ configs/mcp_config.yaml>`
- Kiểm tra URL trong `configs/mcp_config.yaml` - đây là nơi duy nhất để cấu hình
- Kiểm tra internet connection và firewall settings

### Tool loading errors

- Kiểm tra MCP server đang chạy và accessible
- Kiểm tra log để xem lỗi cụ thể
- Thử restart MCP server
