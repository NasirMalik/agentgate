from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from agentgate.shared.protocol import HEADER_AGENT_REQUEST


class AgentDetectionMiddleware(BaseHTTPMiddleware):
    """Sets request.state.is_agent_request based on X-Agent-Request header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.is_agent_request = (
            request.headers.get(HEADER_AGENT_REQUEST, "").lower() == "true"
        )
        return await call_next(request)
