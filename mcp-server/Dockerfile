# Deliberately its own image, not a layer on the backend.
#
# The MCP SDK requires a much newer starlette than FastAPI 0.115 allows, so the
# two cannot share an interpreter: installing mcp into the backend breaks
# FastAPI's router at import time. Separate images, separate dependency trees,
# and the MCP server reaches the platform over HTTP like any other client.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Streamable HTTP endpoint for remote agents.
EXPOSE 8081

# Overridden by docker-compose for the HTTP transport; stdio is the default so
# the image also works when an agent spawns it directly.
ENTRYPOINT ["mcp-server-life-guardian"]
