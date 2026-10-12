"""OCR API Client module."""
import asyncio
from typing import Any, Self

import httpx


class _SyncASGITransport(httpx.BaseTransport):
    """Synchronous adapter for ASGI applications and ASGITransport."""

    def __init__(self, app_or_transport: Any | httpx.ASGITransport) -> None:
        if isinstance(app_or_transport, httpx.ASGITransport):
            self._async_transport = app_or_transport
        else:
            self._async_transport = httpx.ASGITransport(app=app_or_transport)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        timeout_dict = request.extensions.get("timeout", {})
        timeout = timeout_dict.get("read") or timeout_dict.get("connect") or 5.0

        async def _do_request() -> httpx.Response:
            resp = await self._async_transport.handle_async_request(request)
            content = await resp.aread()
            return httpx.Response(
                status_code=resp.status_code,
                headers=resp.headers,
                content=content,
                request=request,
            )

        try:
            return asyncio.run(asyncio.wait_for(_do_request(), timeout=timeout))
        except TimeoutError:
            raise httpx.ReadTimeout(
                f"Request timed out after {timeout} seconds",
                request=request,
            )

    def close(self) -> None:
        asyncio.run(self._async_transport.aclose())


class OCRClient:
    """Client for interacting with the OCR API service."""

    def __init__(
        self,
        base_url: str = "http://testserver",
        app: Any | None = None,
        transport: httpx.BaseTransport | httpx.ASGITransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the OCR Client with base URL, ASGI app, or transport.

        Args:
            base_url: Base URL for the OCR service.
            app: FastAPI/ASGI application instance for in-memory testing.
            transport: Custom HTTPX transport instance.
            timeout: Default request timeout in seconds.
        """
        self.base_url = base_url
        if app is not None:
            sync_transport = _SyncASGITransport(app)
            self._client = httpx.Client(
                transport=sync_transport,
                base_url=self.base_url,
                timeout=timeout,
            )
        elif isinstance(transport, httpx.ASGITransport):
            sync_transport = _SyncASGITransport(transport)
            self._client = httpx.Client(
                transport=sync_transport,
                base_url=self.base_url,
                timeout=timeout,
            )
        elif transport is not None:
            self._client = httpx.Client(
                transport=transport,
                base_url=self.base_url,
                timeout=timeout,
            )
        else:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
            )

    def extract_document(self) -> httpx.Response:
        """Call standard OCR extraction endpoint.

        Returns:
            httpx.Response with extracted document data.
        """
        return self._client.post("/ocr/extraer")

    def extract_illegible_document(self) -> httpx.Response:
        """Call illegible document OCR extraction endpoint.

        Returns:
            httpx.Response with extraction failure details.
        """
        return self._client.post("/ocr/extraer/ilegible")

    def extract_with_timeout(self, timeout: float = 1.0) -> httpx.Response:
        """Call slow provider endpoint with custom timeout.

        Args:
            timeout: Maximum time in seconds to wait for response.

        Returns:
            httpx.Response if successful within timeout limit.
        """
        return self._client.post("/ocr/extraer/timeout", timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
