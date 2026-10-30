"""Model-agnostic API provider for document normalization over HTTPS."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

from normalizer.providers.masking import mask_dump_for_provider

logger = logging.getLogger(__name__)


class ApiProvider:
    """Model-agnostic API provider transmitting masked payloads over secure HTTPS."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        max_chars: int = 20000,
        max_images: int = 5,
        max_retries: int = 3,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        raw_key = api_key or os.environ.get("NORMALIZER_API_KEY")
        raw_url = api_url or os.environ.get("NORMALIZER_API_URL")

        if not raw_key:
            raise ValueError("NORMALIZER_API_KEY environment variable is required")

        if not raw_url:
            raise ValueError("NORMALIZER_API_URL environment variable is required")

        if not raw_url.startswith("https://"):
            # CRITICAL: Never reflect the actual URL or key in the exception message
            raise ValueError("NORMALIZER_API_URL must use https:// scheme")

        self.api_key = raw_key
        self.api_url = raw_url
        self.max_chars = max_chars
        self.max_images = max_images
        self.max_retries = max_retries
        self.timeout = timeout

    def normalize(
        self,
        dump: dict[str, Any],
        images: list[Path] | None = None,
        with_images: bool = False,
        dry_run: bool = False,
        dry_run_path: Path | None = None,
    ) -> dict[str, Any]:
        """Normalize extracted document dump via external HTTPS API."""
        masked_dump, _ = mask_dump_for_provider(dump)

        if with_images:
            print(
                "ADVERTENCIA: Las capturas de pantalla no admiten enmascaramiento automático y pueden contener datos visibles.",
                file=sys.stderr,
            )

        # Prepare payload
        payload: dict[str, Any] = {
            "dump": masked_dump,
        }

        if with_images and images:
            selected_images = images[: self.max_images]
            payload["images"] = [str(p) for p in selected_images]

        # Handle --dry-run
        if dry_run:
            out_path = dry_run_path
            if out_path is None:
                doc_id = (
                    dump.get("meta", {}).get("identificador del caso")
                    or dump.get("meta", {}).get("identificador")
                    or "default"
                )
                out_path = Path("build") / str(doc_id) / "dry_run_payload.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return {"meta": masked_dump.get("meta", {}), "cases": []}

        # Telemetry: record metric counts, NEVER content
        payload_json = json.dumps(payload, ensure_ascii=False)
        char_count = len(payload_json)
        img_count = len(payload.get("images", []))
        logger.info(
            "API request scheduled: chars=%d, images=%d, max_retries=%d",
            char_count,
            img_count,
            self.max_retries,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        session = requests.Session()
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            t_start = time.perf_counter()
            try:
                response = session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                latency = time.perf_counter() - t_start
                logger.info(
                    "API response received: attempt=%d, status=%d, latency=%.3fs",
                    attempt,
                    response.status_code,
                    latency,
                )

                if response.status_code >= 500:
                    last_exception = requests.exceptions.HTTPError(
                        f"Server error HTTP {response.status_code}"
                    )
                    time.sleep(0.1 * attempt)
                    continue

                if response.status_code >= 400:
                    raise requests.exceptions.HTTPError(
                        f"Client error HTTP {response.status_code}"
                    )

                return response.json()

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                latency = time.perf_counter() - t_start
                logger.warning(
                    "Network error during attempt %d: latency=%.3fs",
                    attempt,
                    latency,
                )
                last_exception = exc
                time.sleep(0.1 * attempt)

        if last_exception:
            raise last_exception

        raise RuntimeError("API request failed with unknown error")
