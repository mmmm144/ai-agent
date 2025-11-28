# VNStock Agent với Google ADK

Agent sử dụng Google ADK với MCPToolset để tích hợp với VNStock MCP Server.

## Cài đặt

```bash
uv sync
```

## Sử dụng

### Chạy với ADK Web

```bash
adk web --port 8001
```

Agent sẽ tự động load MCP tools từ `vnstock-mcp-server` qua stdio transport.

### Cấu trúc

```
test-adk/
├── agents/
│   ├── __init__.py    # Export root_agent
│   └── agent.py       # Agent chính với MCPToolset
├── pyproject.toml     # Dependencies
└── README.md          # Documentation
```

## MCP Server

Agent kết nối với MCP server qua HTTP transport (JSON-RPC).

### Cấu hình

**Cấu hình chính nằm ở `configs/mcp_config.yaml`** - đây là nơi duy nhất để thay đổi URL và timeout:

```yaml
mcp_server:
  url: "https://mcp-server-vietnam-stock-trading.onrender.com"
  transport: "streamable-http"
  timeout: 30
```

**Có thể override bằng biến môi trường** (ưu tiên hơn config file):

```bash
# Windows (PowerShell)
$env:MCP_SERVER_URL="https://custom-url.com"
$env:MCP_TIMEOUT="15.0"

# Windows (CMD)
set MCP_SERVER_URL=https://custom-url.com
set MCP_TIMEOUT=15.0

# Linux/Mac
export MCP_SERVER_URL="https://custom-url.com"
export MCP_TIMEOUT="15.0"
```

### MCP Server

MCP server đã được deploy trên Render. URL mặc định được cấu hình trong `configs/mcp_config.yaml`.

Không cần chạy local MCP server, agent sẽ tự động kết nối đến server trên cloud theo cấu hình.

## Tools Available

32 tools từ VNStock MCP Server:

### Company Tools (11)

- `get_company_overview` - Tổng quan công ty
- `get_company_news` - Tin tức công ty
- `get_company_events` - Sự kiện công ty
- `get_company_shareholders` - Cổ đông
- `get_company_officers` - Cán bộ điều hành
- `get_company_subsidiaries` - Công ty con
- `get_company_reports` - Báo cáo
- `get_company_dividends` - Cổ tức
- `get_company_insider_deals` - Giao dịch nội bộ
- `get_company_ratio_summary` - Tổng hợp tỷ lệ tài chính
- `get_company_trading_stats` - Thống kê giao dịch

### Quote Tools (3)

- `get_quote_history_price` - Lịch sử giá
- `get_quote_intraday_price` - Giá trong ngày
- `get_quote_price_depth` - Độ sâu giá (order book)

### Finance Tools (5)

- `get_income_statements` - Báo cáo thu nhập
- `get_balance_sheets` - Bảng cân đối kế toán
- `get_cash_flows` - Báo cáo lưu chuyển tiền tệ
- `get_finance_ratios` - Tỷ lệ tài chính
- `get_raw_report` - Báo cáo thô

### Fund Tools (6)

- `list_all_funds` - Danh sách quỹ
- `search_fund` - Tìm kiếm quỹ
- `get_fund_nav_report` - Báo cáo NAV
- `get_fund_top_holding` - Danh mục đầu tư hàng đầu
- `get_fund_industry_holding` - Phân bổ ngành
- `get_fund_asset_holding` - Phân bổ tài sản

### Listing Tools (5)

- `get_all_symbol_groups` - Danh sách nhóm mã
- `get_all_industries` - Danh sách ngành
- `get_all_symbols_by_group` - Mã theo nhóm
- `get_all_symbols_by_industry` - Mã theo ngành
- `get_all_symbols` - Tất cả mã chứng khoán

### Trading Tools (1)

- `get_price_board` - Bảng giá

### Misc Tools (2)

- `get_gold_price` - Giá vàng
- `get_exchange_rate` - Tỷ giá hối đoái

**Tổng cộng: 32 tools**

## Lưu ý

- **Cấu hình MCP server nằm ở `configs/mcp_config.yaml`** - chỉnh sửa URL/timeout ở đây
- Agent kết nối với MCP server qua HTTP (JSON-RPC)
- MCP server đã được deploy trên Render, không cần chạy local
- Agent tự động load tất cả tools từ MCP server khi khởi tạo
- `adk web --port 8001` sẽ tự động load `root_agent` từ `agents/` module

## Troubleshooting

### Không thể kết nối đến MCP server

**Nguyên nhân**: MCP server không accessible hoặc có vấn đề về mạng.

**Giải pháp**:

1. **Kiểm tra MCP server đang chạy**:

   ```bash
   # Lấy URL từ configs/mcp_config.yaml
   curl <URL_từ_config>
   ```

2. **Kiểm tra internet connection**: Đảm bảo có kết nối internet để truy cập Render server.

3. **Thay đổi URL**: Chỉnh sửa trong `configs/mcp_config.yaml` hoặc sử dụng biến môi trường để override

4. **Kiểm tra firewall/proxy**: Đảm bảo firewall không chặn HTTPS connections đến Render.

### Không load được tools

**Nguyên nhân**: MCP server không trả về tools hoặc có lỗi.

**Giải pháp**:

1. Kiểm tra log khi chạy agent - sẽ hiển thị số lượng tools đã load và config file path
2. Kiểm tra MCP server có hỗ trợ `tools/list` endpoint không
3. Kiểm tra response từ MCP server: `curl -X POST <URL_từ_configs/mcp_config.yaml> -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`

## License

MIT License

## Tài liệu tham khảo

- [Google ADK Documentation](https://ai.google.dev/adk)
- [VNStock MCP Server](https://github.com/hypersense/vnstock-mcp-server)
- [VNStock Library](https://github.com/thinh-vu/vnstock)
# ai-agent
