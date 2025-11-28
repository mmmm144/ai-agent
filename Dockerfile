# Minimal Dockerfile for test-adk
# Builds a container that runs the FastAPI app (uvicorn) and initializes ADK agent

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for common wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc git curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY README.md .
# Copy the rest of the app
COPY app ./app
COPY agents ./agents
COPY configs ./configs
COPY scripts ./scripts
COPY run_server.py ./run_server.py
COPY start_server.sh ./start_server.sh

# Install python deps
RUN python -m pip install --upgrade pip setuptools wheel
# Install the package defined by pyproject.toml
RUN pip install .

# Expose port (default 8002 used by run_server.py)
EXPOSE 8002

# Default command: run uvicorn directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]
