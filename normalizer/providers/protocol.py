"""Protocol definition for normalizer providers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NormalizerProvider(Protocol):
    """Protocol defining the interface for document normalizer providers."""

    def normalize(
        self,
        dump: dict[str, Any],
        images: list[Path] | None = None,
        with_images: bool = False,
        dry_run: bool = False,
        dry_run_path: Path | None = None,
    ) -> dict[str, Any]:
        """Normalize extracted document dump into a normalized specification dictionary."""
        ...
