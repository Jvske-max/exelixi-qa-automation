"""Agent file provider reading pre-generated normalized JSON from disk without network access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from normalizer.providers.masking import mask_dump_for_provider


class AgentFileProvider:
    """Default provider that loads normalized specifications from disk without network calls."""

    def __init__(
        self,
        normalized_dir: Path | str | None = None,
        stem: str | None = None,
    ) -> None:
        self.normalized_dir = Path(normalized_dir) if normalized_dir else Path("normalized")
        self.stem = stem

    def normalize(
        self,
        dump: dict[str, Any],
        images: list[Path] | None = None,
        with_images: bool = False,
        dry_run: bool = False,
        dry_run_path: Path | None = None,
    ) -> dict[str, Any]:
        """Normalize extracted document dump by loading normalized/<stem>.json."""
        if dry_run:
            masked_dump, _ = mask_dump_for_provider(dump)
            out_path = dry_run_path
            if out_path is None:
                doc_id = (
                    dump.get("meta", {}).get("identificador del caso")
                    or dump.get("meta", {}).get("identificador")
                    or self.stem
                    or "default"
                )
                out_path = Path("build") / str(doc_id) / "dry_run_payload.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps({"dump": masked_dump}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return {"meta": masked_dump.get("meta", {}), "cases": []}

        # Resolve candidate JSON paths strictly matching stem or identifiers
        target_path: Path | None = None

        if self.stem:
            direct_candidate = self.normalized_dir / f"{self.stem}.json"
            if direct_candidate.exists():
                target_path = direct_candidate
            else:
                raise FileNotFoundError(
                    f"Normalized file not found: {self.normalized_dir}/{self.stem}.json"
                )

        if target_path is None:
            # Try to infer stem from dump fields
            meta = dump.get("meta", {})
            candidates = [
                dump.get("stem"),
                dump.get("source_stem"),
                meta.get("identificador del caso"),
                meta.get("identificador"),
                meta.get("caso_id"),
            ]
            for cand in candidates:
                if cand:
                    p = self.normalized_dir / f"{cand}.json"
                    if p.exists():
                        target_path = p
                        break

        if target_path is None or not target_path.exists():
            stem_label = self.stem or dump.get("stem") or "<stem>"
            raise FileNotFoundError(
                f"Normalized file not found: {self.normalized_dir}/{stem_label}.json"
            )

        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
