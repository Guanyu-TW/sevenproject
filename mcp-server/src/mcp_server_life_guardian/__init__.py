"""AI 智慧管家 MCP server.

Entry point shaped like the reference servers in modelcontextprotocol/servers:
an argparse ``main()`` that picks a transport and runs ``serve()``.
"""

from __future__ import annotations

import logging
import os

from mcp_server_life_guardian.client import DEFAULT_TIMEOUT, LifeGuardianClient
from mcp_server_life_guardian.server import build_server

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "http://localhost:8000"


async def serve(
    *,
    api_base_url: str,
    transport: str,
    host: str,
    port: int,
    timeout: float,
    allowed_hosts: list[str] | None,
    allowed_origins: list[str] | None,
) -> None:
    """Run the MCP server over ``transport`` against ``api_base_url``."""
    client = LifeGuardianClient(api_base_url, timeout=timeout)
    mcp = build_server(client)

    if transport == "stdio":
        # Nothing may be written to stdout except protocol frames.
        logger.info("MCP stdio server ready, API at %s", api_base_url)
        await mcp.run_stdio_async()
        return

    # Streamable HTTP. DNS-rebinding protection is on by default and only
    # accepts requests addressed to localhost, so anything reachable under a
    # real hostname has to be listed explicitly or every request gets a 421.
    kwargs: dict[str, object] = {"host": host, "port": port}
    if allowed_hosts or allowed_origins:
        from mcp.server.transport_security import TransportSecuritySettings

        kwargs["transport_security"] = TransportSecuritySettings(
            allowed_hosts=allowed_hosts or [],
            allowed_origins=allowed_origins or [],
        )
        logger.info(
            "transport security: hosts=%s origins=%s", allowed_hosts, allowed_origins
        )
    else:
        logger.warning(
            "No --allowed-host given: only requests addressed to localhost are "
            "accepted. Remote agents will get HTTP 421."
        )

    logger.info(
        "MCP streamable-http server on http://%s:%s/mcp, API at %s",
        host,
        port,
        api_base_url,
    )
    await mcp.run_streamable_http_async(**kwargs)  # type: ignore[arg-type]


def main() -> None:
    """CLI for the AI 智慧管家 MCP server."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        prog="mcp-server-life-guardian",
        description=(
            "Expose the AI 智慧管家 smart-community platform as MCP tools so "
            "external agents can analyse demands, match vendors and drive cases."
        ),
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("LIFE_GUARDIAN_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="Base URL of the platform REST API (env: LIFE_GUARDIAN_API_BASE_URL).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="stdio for a locally spawned server, streamable-http for remote agents.",
    )
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("MCP_PORT", "8081"))
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("MCP_API_TIMEOUT", DEFAULT_TIMEOUT)),
        help="Seconds to wait on the platform API; LLM-backed calls are slow.",
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=_env_list("MCP_ALLOWED_HOSTS"),
        help=(
            "Hostname[:port] this server is served behind. Repeatable. Required "
            "for streamable-http behind anything other than localhost."
        ),
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=_env_list("MCP_ALLOWED_ORIGINS"),
        help="Browser Origin allowed to call this server. Repeatable.",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("MCP_LOG_LEVEL", "INFO"),
        help="Python logging level.",
    )

    args = parser.parse_args()

    # stderr, never stdout: on stdio the transport owns stdout.
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(
        serve(
            api_base_url=args.api_base_url,
            transport=args.transport,
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            allowed_hosts=args.allowed_host,
            allowed_origins=args.allowed_origin,
        )
    )


def _env_list(name: str) -> list[str]:
    """Comma-separated env var to list, so Docker can supply repeatable flags."""
    raw = os.environ.get(name, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


if __name__ == "__main__":
    main()
