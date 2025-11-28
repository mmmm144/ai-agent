"""
VNStock Agent sử dụng MCP tools từ VNStock MCP Server qua HTTP.

Sử dụng JSON-RPC over HTTP (streamable-http transport).
FastMCP streamable-http sử dụng SSE format cho response.

Cấu hình MCP server được đọc từ configs/mcp_config.yaml.
Có thể override bằng biến môi trường MCP_SERVER_URL và MCP_TIMEOUT.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
import yaml
from google.adk.agents import LlmAgent
from dotenv import load_dotenv

# Load biến môi trường (GOOGLE_API_KEY, v.v.) từ .env nếu có
load_dotenv()

# Load cấu hình MCP từ configs/mcp_config.yaml
_CONFIG_DIR = Path(__file__).parent.parent / "configs"
_CONFIG_FILE = _CONFIG_DIR / "mcp_config.yaml"


def _load_mcp_config() -> Dict[str, Any]:
    """Load cấu hình MCP từ configs/mcp_config.yaml."""
    try:
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("mcp_server", {})
    except Exception as e:
        print(f"Warning: Failed to load config from {_CONFIG_FILE}: {e}")
    return {}


# Load config
_mcp_config = _load_mcp_config()

# MCP Server URL - ưu tiên: environment variable > config file > default
MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    _mcp_config.get("url", "https://mcp-server-vietnam-stock-trading.onrender.com"),
)
MCP_TIMEOUT = float(os.getenv("MCP_TIMEOUT", str(_mcp_config.get("timeout", 30.0))))

# Session ID cho MCP server (sẽ được lấy sau khi initialize)
_mcp_session_id: Optional[str] = None


def _parse_sse_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse SSE (Server-Sent Events) response từ FastMCP streamable-http."""
    try:
        # Tìm dòng bắt đầu với "data:"
        lines = response_text.strip().split("\n")
        for line in lines:
            if line.startswith("data: "):
                json_str = line[6:]  # Bỏ "data: "
                return json.loads(json_str)
        return None
    except Exception as e:
        print(f"Error parsing SSE response: {e}")
        return None


def _initialize_mcp_session() -> Optional[str]:
    """Khởi tạo MCP session và lấy session ID từ FastMCP streamable-http."""
    global _mcp_session_id

    if _mcp_session_id:
        return _mcp_session_id

    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            # Gọi initialize method
            payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "vnstock-adk-agent",
                        "version": "1.0.0",
                    },
                },
                "id": 1,
            }

            endpoints_to_try = ["/mcp", "/"]
            for endpoint in endpoints_to_try:
                try:
                    url = f"{MCP_SERVER_URL}{endpoint}"
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    }

                    resp = client.post(url, json=payload, headers=headers)

                    if resp.status_code == 404 and endpoint != endpoints_to_try[-1]:
                        continue

                    if resp.status_code != 200:
                        print(f"Initialize failed: HTTP {resp.status_code}")
                        if endpoint != endpoints_to_try[-1]:
                            continue
                        return None

                    # Lấy session ID từ response header (FastMCP trả về trong mcp-session-id)
                    session_id = resp.headers.get("mcp-session-id") or resp.headers.get(
                        "Mcp-Session-Id"
                    )

                    if not session_id:
                        print("Warning: No session ID in initialize response")
                        if endpoint != endpoints_to_try[-1]:
                            continue
                        return None

                    # Parse SSE response
                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/event-stream" in content_type:
                        # Response là SSE format
                        result = _parse_sse_response(resp.text)
                    else:
                        # Response là JSON thông thường
                        try:
                            result = resp.json()
                        except json.JSONDecodeError:
                            result = None

                    if result and "error" in result:
                        error_msg = result["error"].get("message", "Unknown error")
                        print(f"Error initializing MCP session: {error_msg}")
                        return None

                    # Lưu session ID
                    _mcp_session_id = session_id
                    # print(f"MCP session initialized: {session_id[:8]}...")

                    # Gọi initialized notification (theo MCP spec)
                    try:
                        initialized_payload = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        }
                        init_headers = headers.copy()
                        init_headers["mcp-session-id"] = session_id
                        client.post(url, json=initialized_payload, headers=init_headers)
                    except Exception as e:
                        print(f"Warning: Failed to send initialized notification: {e}")

                    return session_id

                except httpx.HTTPStatusError as e:
                    if (
                        e.response.status_code == 404
                        and endpoint != endpoints_to_try[-1]
                    ):
                        continue
                    print(f"Error initializing session: HTTP {e.response.status_code}")
                    return None

    except Exception as e:
        print(f"Error initializing MCP session: {e}")
        return None

    return None


def _call_mcp_jsonrpc(
    method: str, params: Optional[Dict[str, Any]] = None, request_id: int = 1
) -> Dict[str, Any]:
    """Gọi MCP server qua JSON-RPC over HTTP (streamable-http transport)."""
    global _mcp_session_id

    # Đảm bảo session đã được initialize
    if not _mcp_session_id:
        session_result = _initialize_mcp_session()
        if not session_result:
            return {
                "error": "Failed to initialize MCP session",
                "method": method,
            }

    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
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
                    url = f"{MCP_SERVER_URL}{endpoint}"
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": _mcp_session_id,  # FastMCP yêu cầu session ID trong header
                    }

                    resp = client.post(url, json=payload, headers=headers)

                    if resp.status_code == 404 and endpoint != endpoints_to_try[-1]:
                        continue

                    resp.raise_for_status()

                    # Parse response (có thể là SSE hoặc JSON)
                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/event-stream" in content_type:
                        # Response là SSE format
                        result = _parse_sse_response(resp.text)
                    else:
                        # Response là JSON thông thường
                        try:
                            result = resp.json()
                        except json.JSONDecodeError:
                            return {
                                "error": "Invalid JSON response",
                                "method": method,
                                "response": resp.text[:200],
                            }

                    if not result:
                        return {
                            "error": "Failed to parse response",
                            "method": method,
                        }

                    if "error" in result:
                        return {
                            "error": result["error"].get("message", "Unknown error"),
                            "code": result["error"].get("code"),
                            "method": method,
                        }

                    return result.get("result", result)

                except httpx.HTTPStatusError as e:
                    if (
                        e.response.status_code == 404
                        and endpoint != endpoints_to_try[-1]
                    ):
                        continue
                    return {
                        "error": f"HTTP {e.response.status_code}: {e.response.text}",
                        "method": method,
                        "endpoint": endpoint,
                    }

            return {
                "error": "Failed to connect to MCP server",
                "method": method,
                "note": f"Tried endpoints: {endpoints_to_try}",
            }

    except Exception as e:
        return {
            "error": str(e),
            "method": method,
            "note": f"Failed to call MCP server at {MCP_SERVER_URL}",
        }


def _process_arguments(
    tool_name: str, properties: Dict, tool_param_mapping: Dict, **kwargs
):
    """Process và validate arguments từ kwargs."""
    processed_kwargs = {}

    # Áp dụng parameter mapping nếu có
    normalized_kwargs = {}
    for key, value in kwargs.items():
        # Kiểm tra xem có mapping không
        if key in tool_param_mapping:
            normalized_key = tool_param_mapping[key]
            normalized_kwargs[normalized_key] = value
        else:
            normalized_kwargs[key] = value

    # Xử lý từng parameter
    for param_name, param_value in normalized_kwargs.items():
        if param_name not in properties:
            # Nếu tham số không có trong schema, giữ nguyên (có thể là optional)
            processed_kwargs[param_name] = param_value
            continue

        param_schema = properties[param_name]
        param_type = param_schema.get("type")

        # Xử lý đặc biệt cho get_price_board: symbols phải là list
        if tool_name == "get_price_board" and param_name == "symbols":
            if isinstance(param_value, str):
                # Nếu là string, convert thành list
                processed_kwargs[param_name] = [param_value]
            elif isinstance(param_value, list):
                processed_kwargs[param_name] = param_value
            else:
                # Nếu là giá trị khác, thử convert thành list
                processed_kwargs[param_name] = [str(param_value)]
        # Xử lý array/list types
        elif param_type == "array" or (
            isinstance(param_type, list) and "array" in param_type
        ):
            if isinstance(param_value, str):
                # Nếu là string nhưng schema yêu cầu array, convert thành list
                processed_kwargs[param_name] = [param_value]
            elif isinstance(param_value, list):
                processed_kwargs[param_name] = param_value
            else:
                # Nếu là giá trị khác, thử convert thành list
                processed_kwargs[param_name] = [param_value]
        # Xử lý string types: nếu tool cần string nhưng nhận list, lấy phần tử đầu tiên
        elif param_type == "string":
            if isinstance(param_value, list):
                # Nếu là list nhưng schema yêu cầu string, lấy phần tử đầu tiên
                if len(param_value) > 0:
                    processed_kwargs[param_name] = str(param_value[0])
                else:
                    processed_kwargs[param_name] = ""
            else:
                # Convert sang string nếu cần
                processed_kwargs[param_name] = str(param_value)
        else:
            # Giữ nguyên giá trị cho các type khác
            processed_kwargs[param_name] = param_value

    return processed_kwargs


def _create_mcp_tool_function(tool_name: str, tool_schema: Dict[str, Any]):
    """Tạo function tool từ MCP tool schema."""
    description = tool_schema.get("description", f"MCP tool: {tool_name}")
    input_schema = tool_schema.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Mapping các parameter names phổ biến (LLM có thể dùng tên khác)
    # Áp dụng cho tất cả tools: nếu tool cần "symbol" (số ít) nhưng LLM truyền "symbols" (số nhiều), map lại
    # Ngược lại, nếu tool cần "symbols" (số nhiều) nhưng LLM truyền "symbol" (số ít), map lại
    tool_param_mapping = {}

    # Kiểm tra xem tool có parameter "symbol" hay "symbols"
    has_symbols = "symbols" in properties
    has_symbol = "symbol" in properties

    if has_symbols:
        # Tool cần "symbols" (list), map các biến thể thành "symbols"
        tool_param_mapping = {
            "symbol": "symbols",  # LLM có thể dùng "symbol" (số ít)
            "symbol_list": "symbols",
            "stocks": "symbols",
            "stock": "symbols",
        }
    elif has_symbol:
        # Tool cần "symbol" (string), map các biến thể thành "symbol"
        tool_param_mapping = {
            "symbols": "symbol",  # LLM có thể dùng "symbols" (số nhiều)
            "symbol_list": "symbol",
            "stocks": "symbol",
            "stock": "symbol",
        }

    # Mapping cụ thể cho từng tool (override nếu cần)
    specific_mappings = {
        "get_price_board": {
            "symbol": "symbols",
            "symbol_list": "symbols",
            "stocks": "symbols",
            "stock": "symbols",
        },
    }
    if tool_name in specific_mappings:
        tool_param_mapping = specific_mappings[tool_name]

    # Tạo docstring chi tiết từ schema để ADK hiểu được parameters
    docstring_parts = [description or f"MCP tool: {tool_name}", "", "Parameters:"]
    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "Any")
        param_desc = param_schema.get("description", "")
        is_required = param_name in required
        default = param_schema.get("default")

        param_line = f"  {param_name} ({param_type})"
        if not is_required and default is not None:
            param_line += f" = {default}"
        elif not is_required:
            param_line += " (optional)"
        if param_desc:
            param_line += f": {param_desc}"
        docstring_parts.append(param_line)

    full_docstring = "\n".join(docstring_parts)

    # Tạo function signature từ properties
    # Xây dựng parameter list cho function signature
    param_signatures = []
    param_defaults = {}

    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "Any")
        default = param_schema.get("default")
        is_required = param_name in required

        # Tạo type annotation string
        if param_type == "array":
            # FIX: Gemini API yêu cầu List[item_type] thay vì list
            items_schema = param_schema.get("items", {})
            items_type = items_schema.get("type", "str")
            if items_type == "string":
                type_annotation = "List[str]"
            elif items_type == "integer":
                type_annotation = "List[int]"
            elif items_type == "number":
                type_annotation = "List[float]"
            else:
                type_annotation = "List[Any]"
        elif param_type == "string":
            type_annotation = "str"
        elif param_type == "integer":
            type_annotation = "int"
        elif param_type == "number":
            type_annotation = "float"
        elif param_type == "boolean":
            type_annotation = "bool"
        else:
            type_annotation = "Any"

        if is_required and default is None:
            # Required parameter, không có default
            param_signatures.append(f"{param_name}: {type_annotation}")
        else:
            # Optional parameter với default
            if default is not None:
                if isinstance(default, str):
                    default_str = f'"{default}"'
                else:
                    default_str = str(default)
                param_signatures.append(
                    f"{param_name}: {type_annotation} = {default_str}"
                )
            else:
                # Optional nhưng không có default value, dùng Optional[type] = None
                # ADK yêu cầu Optional[type] thay vì type = None
                param_signatures.append(
                    f"{param_name}: Optional[{type_annotation}] = None"
                )

    # Tạo function với signature rõ ràng bằng exec
    # Đây là cách duy nhất để ADK có thể parse được parameters
    import inspect

    # Build function body
    func_body_lines = [
        f'    """{full_docstring}"""',
        "    # Collect arguments",
        "    import inspect as _inspect",
        "    frame = _inspect.currentframe()",
        "    args_info = _inspect.getargvalues(frame)",
        "    kwargs = {}",
        "    for arg_name in args_info.args:",
        "        if arg_name in args_info.locals:",
        "            kwargs[arg_name] = args_info.locals[arg_name]",
        "",
        f"    # Process arguments với tool_name='{tool_name}'",
        f"    _tool_name = '{tool_name}'",
        f"    _properties = {properties}",
        f"    _tool_param_mapping = {tool_param_mapping}",
        "",
        "    # Process arguments",
        "    processed_kwargs = _process_arguments_func(_tool_name, _properties, _tool_param_mapping, **kwargs)",
        "",
        "    # Debug log",
        "    print(f'[DEBUG] {_tool_name} called with kwargs: {kwargs}')",
        "    print(f'[DEBUG] {_tool_name} processed to: {processed_kwargs}')",
        "",
        "    # Call MCP server",
        "    result = _call_mcp_jsonrpc_func(",
        '        method="tools/call",',
        "        params={'name': _tool_name, 'arguments': processed_kwargs},",
        "    )",
        "",
        "    if 'error' in result:",
        "        error_msg = result.get('error', 'Unknown error')",
        "        print(f'[ERROR] {_tool_name} failed: {error_msg}')",
        "        print(f'[ERROR] Processed arguments: {processed_kwargs}')",
        "        return {",
        "            'error': error_msg,",
        "            'tool': _tool_name,",
        "            'code': result.get('code'),",
        "        }",
        "",
        "    # Trả về content nếu có",
        "    if 'content' in result:",
        "        if isinstance(result['content'], list):",
        "            texts = []",
        "            for item in result['content']:",
        "                if isinstance(item, dict):",
        "                    if 'text' in item:",
        "                        texts.append(item['text'])",
        "                    elif 'type' in item and item.get('type') == 'text':",
        "                        texts.append(item.get('text', ''))",
        "            if texts:",
        "                return '\\n'.join(texts)",
        "        return result['content']",
        "    if 'text' in result:",
        "        return result['text']",
        "",
        "    return result",
    ]

    func_body = "\n".join(func_body_lines)
    func_def = f"def {tool_name}({', '.join(param_signatures)}):\n{func_body}"

    # Execute để tạo function
    # Pass các functions cần thiết vào namespace để function có thể sử dụng
    namespace = {
        "__name__": __name__,
        "__builtins__": __builtins__,
        "Any": Any,  # Import Any để dùng trong function signature
        "Optional": Optional,  # Import Optional để dùng trong function signature
        "List": List,  # Import List để dùng trong function signature (List[str], List[int], etc.)
        "_call_mcp_jsonrpc_func": _call_mcp_jsonrpc,  # Alias để tránh conflict
        "_process_arguments_func": _process_arguments,  # Alias để tránh conflict
        "print": print,  # Đảm bảo print function có sẵn
    }
    exec(func_def, namespace)
    tool_function = namespace[tool_name]

    return tool_function


def _load_mcp_tools_via_http() -> List[Any]:
    """Load MCP tools từ server qua HTTP."""
    tools = []
    try:
        # List tools từ MCP server
        result = _call_mcp_jsonrpc(method="tools/list")

        if "error" in result:
            print(f"Error listing MCP tools: {result.get('error')}")
            print(f"Note: Ensure MCP server is running at {MCP_SERVER_URL}")
            print(f"Config file: {_CONFIG_FILE}")
            return []

        tools_list = result.get("tools", [])

        if not tools_list:
            print("Warning: No tools found from MCP server")
            return []

        # Tạo function tools
        for tool in tools_list:
            tool_name = tool.get("name")
            if tool_name:
                tool_func = _create_mcp_tool_function(tool_name, tool)
                tools.append(tool_func)
                # print(f"Loaded MCP tool: {tool_name}")

        print(f"Successfully loaded {len(tools)} MCP tools from {MCP_SERVER_URL}")

    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        print(f"Note: Ensure MCP server is running at {MCP_SERVER_URL}")
        print(f"Config file: {_CONFIG_FILE}")

    return tools


def get_current_datetime():
    """
    Lấy ngày và giờ hiện tại (thời gian thực từ hệ thống).

    Returns:
        dict: Dictionary chứa thông tin ngày/giờ hiện tại với các format khác nhau:
            - date: YYYY-MM-DD
            - time: HH:MM:SS
            - datetime: YYYY-MM-DD HH:MM:SS
            - date_vn: DD/MM/YYYY
            - day_name: Tên thứ bằng tiếng Anh
            - day_name_vn: Tên thứ bằng tiếng Việt
            - full_vn: "DD tháng MM năm YYYY" (ví dụ: "09 tháng 11 năm 2024")

    Example:
        >>> result = get_current_datetime()
        >>> print(result["full_vn"])
        "09 tháng 11 năm 2024"
    """
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date_vn": now.strftime("%d/%m/%Y"),
        "day_name": now.strftime("%A"),
        "day_name_vn": {
            "Monday": "Thứ Hai",
            "Tuesday": "Thứ Ba",
            "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm",
            "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy",
            "Sunday": "Chủ Nhật",
        }.get(now.strftime("%A"), now.strftime("%A")),
        "full_vn": f"{now.strftime('%d')} tháng {now.strftime('%m')} năm {now.strftime('%Y')}",
    }


# Load MCP tools từ server
# print(f"Connecting to MCP server at {MCP_SERVER_URL}")
# Initialize session trước khi load tools
_initialize_mcp_session()
tools = _load_mcp_tools_via_http()

# Thêm tool lấy thời gian hiện tại
tools.append(get_current_datetime)
print("Added tool: get_current_datetime")

if not tools:
    print(
        f"Warning: No MCP tools loaded. "
        f"Ensure MCP server is running at {MCP_SERVER_URL}"
    )

# Tạo agent với MCP tools
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="vnstock_agent",
    description=(
        "Assistant chuyên về thị trường chứng khoán Việt Nam. "
        "Có thể truy vấn thông tin công ty, giá cổ phiếu, báo cáo tài chính, "
        "quỹ đầu tư, và các thông tin thị trường khác thông qua VNStock MCP server. "
        "Có thể trả lời các câu hỏi về thời gian thực, giá cả, và phân tích thị trường. "
        "Có tool `get_current_datetime` để lấy ngày/giờ hiện tại chính xác."
    ),
    instruction="""Bạn là một assistant chuyên về thị trường chứng khoán Việt Nam.
Bạn có thể sử dụng các tools từ MCP server để:
- Lấy thông tin công ty: tổng quan, tin tức, sự kiện, cổ đông, cán bộ điều hành, công ty con, cổ tức, giao dịch nội bộ
- Lấy dữ liệu tài chính: báo cáo thu nhập, bảng cân đối kế toán, dòng tiền, tỷ lệ tài chính
- Lấy dữ liệu giá: lịch sử giá, giá trong ngày, độ sâu giá, bảng giá
- Lấy thông tin quỹ: danh sách quỹ, NAV, danh mục đầu tư, phân bổ ngành/tài sản
- Lấy dữ liệu thị trường: danh sách mã chứng khoán, nhóm, ngành
- Lấy dữ liệu khác: giá vàng, tỷ giá hối đoái

QUAN TRỌNG VỀ THỜI GIAN VÀ DỮ LIỆU:
- Khi người dùng hỏi về ngày/giờ hiện tại, LUÔN sử dụng tool `get_current_datetime` để lấy thời gian THỰC TẾ
- KHÔNG BAO GIỜ tự đoán hoặc dùng kiến thức cũ về ngày tháng
- Luôn sử dụng tools để lấy dữ liệu THỰC TẾ từ MCP server
- KHÔNG BAO GIỜ tự tạo hoặc đoán dữ liệu
- Nếu tool trả về dữ liệu, hãy sử dụng dữ liệu đó chính xác
- Nếu tool trả về lỗi, hãy thông báo lỗi rõ ràng cho người dùng
- Luôn kiểm tra kết quả từ tools trước khi trả lời

Khi người dùng hỏi về chứng khoán Việt Nam, hãy:
1. Xác định loại thông tin cần thiết
2. Sử dụng tool phù hợp để lấy dữ liệu THỰC TẾ từ MCP server
3. Kiểm tra kết quả từ tool
4. Phân tích và trình bày kết quả một cách rõ ràng, chính xác, dễ hiểu
5. Nếu không có dữ liệu hoặc có lỗi, hãy giải thích lý do và đề xuất cách khác

Khi người dùng hỏi về ngày/giờ hiện tại:
1. LUÔN gọi tool `get_current_datetime` để lấy thời gian thực
2. Sử dụng kết quả từ tool để trả lời chính xác
3. KHÔNG BAO GIỜ tự đoán hoặc dùng kiến thức cũ về ngày tháng

Luôn trả lời bằng tiếng Việt và cung cấp thông tin chính xác, đầy đủ dựa trên dữ liệu THỰC TẾ từ MCP server.""",
    tools=tools,
)
