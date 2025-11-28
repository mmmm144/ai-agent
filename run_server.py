"""Script để chạy FastAPI server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,  # Port 8002 để tránh conflict với ai-be (port 8000)
        reload=True,  # Auto-reload khi code thay đổi
    )
