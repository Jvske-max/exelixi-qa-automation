"""Evaluation harness measuring normalization quality across document specifications (T7)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from normalizer.extract import extract_document
from normalizer.gaps import detect_gaps, determine_state
from normalizer.grounding import _extract_dump_strings, _normalize_ws_case
from normalizer.schema import NormalizedDoc


@dataclass
class EvaluationRow:
    """Represents an aggregated evaluation row with strict privacy guarantees."""

    order: int
    cases: str
    exec_steps: str
    manual_steps: str
    gaps: str
    quote_pct: str
    status: str

    def to_markdown(self) -> str:
        """Render row as markdown table line."""
        return (
            f"| {self.order} "
            f"| {self.cases} "
            f"| {self.exec_steps} "
            f"| {self.manual_steps} "
            f"| {self.gaps} "
            f"| {self.quote_pct} "
            f"| {self.status} |"
        )


def _find_normalized_json(
    doc_path: Path,
    dump: dict,
    normalized_dir: Path | None,
) -> Path | None:
    """Find matching normalized JSON file in normalized_dir by stem or case ID."""
    if not normalized_dir or not normalized_dir.exists():
        return None

    stem = doc_path.stem
    cand_stem = normalized_dir / f"{stem}.json"
    if cand_stem.is_file():
        return cand_stem

    meta = dump.get("meta", {})
    doc_id = (
        meta.get("identificador del caso")
        or meta.get("identificador")
        or meta.get("id")
        or meta.get("identificador_caso")
    )
    if doc_id and isinstance(doc_id, str):
        cand_id = normalized_dir / f"{doc_id.strip()}.json"
        if cand_id.is_file():
            return cand_id

    m_id = re.search(r"(R-[A-Za-z0-9_-]+)", doc_path.name, re.IGNORECASE)
    if m_id:
        cand_regex = normalized_dir / f"{m_id.group(1)}.json"
        if cand_regex.is_file():
            return cand_regex

    return None


def _format_status_counts(counter: Counter[str]) -> str:
    """Format status counts consistently in priority order."""
    priority = ["READY", "NEEDS_INFO", "UNSUPPORTED"]
    remaining = [k for k in counter if k not in priority]
    parts = [f"{st}: {counter[st]}" for st in priority + remaining if st in counter and counter[st] > 0]
    return ", ".join(parts) if parts else "-"


def evaluate_documents(
    docs_dir: Path | str,
    out_path: Path | str = "build/eval.md",
    normalized_dir: Path | str = "normalized",
) -> str:
    """Evaluate normalization quality and generate strict privacy aggregate markdown report."""
    docs_path = Path(docs_dir)
    out_file = Path(out_path)
    norm_dir = Path(normalized_dir) if normalized_dir else None

    if not docs_path.exists() or not docs_path.is_dir():
        raise FileNotFoundError(f"Documents directory not found or not a directory: {docs_path}")

    # Read all .docx and .pdf files, excluding Word temporary lock files (~$*)
    doc_files = sorted(
        [
            p
            for p in docs_path.iterdir()
            if p.is_file() and p.suffix.lower() in (".docx", ".pdf") and not p.name.startswith("~$")
        ],
        key=lambda p: p.name.lower(),
    )

    rows: list[EvaluationRow] = []

    for idx, doc_path in enumerate(doc_files, start=1):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                dump = extract_document(doc_path, Path(temp_dir))
                gaps = detect_gaps(dump)

                blocking = sum(1 for g in gaps if g.severity == "blocking")
                warning = sum(1 for g in gaps if g.severity == "warning")
                info = sum(1 for g in gaps if g.severity == "info")
                gaps_str = f"B:{blocking} / W:{warning} / I:{info}"

                norm_json_path = _find_normalized_json(doc_path, dump, norm_dir)
                if norm_json_path:
                    with open(norm_json_path, "r", encoding="utf-8") as f:
                        norm_data = json.load(f)
                    norm_doc = NormalizedDoc.model_validate(norm_data)

                    cases_count = len(norm_doc.cases)
                    all_steps = [s for c in norm_doc.cases for s in c.steps]
                    exec_steps = sum(1 for s in all_steps if s.action != "manual")
                    manual_steps = sum(1 for s in all_steps if s.action == "manual")
                    total_steps = exec_steps + manual_steps

                    # Grounding verbatim substring check against extracted dump
                    dump_strings = _extract_dump_strings(dump)
                    normalized_dump_full = " ".join(_normalize_ws_case(s) for s in dump_strings)

                    valid_quotes = 0
                    for s in all_steps:
                        quote_norm = _normalize_ws_case(s.source_quote)
                        if quote_norm and quote_norm in normalized_dump_full:
                            valid_quotes += 1

                    quote_pct_str = f"{(valid_quotes / total_steps) * 100:.1f}%" if total_steps > 0 else "-"

                    status_counter = Counter(c.status for c in norm_doc.cases)
                    status_str = _format_status_counts(status_counter)

                    rows.append(
                        EvaluationRow(
                            order=idx,
                            cases=str(cases_count),
                            exec_steps=str(exec_steps),
                            manual_steps=str(manual_steps),
                            gaps=gaps_str,
                            quote_pct=quote_pct_str,
                            status=status_str,
                        )
                    )
                else:
                    dump_cases = dump.get("cases", [])
                    cases_count = len(dump_cases) if dump_cases else 1

                    case_statuses: list[str] = []
                    for c in dump_cases:
                        n = c.get("n", 1)
                        c_gaps = [
                            g
                            for g in gaps
                            if f"Caso {n}" in g.where or (n == 1 and "Cabecera" in g.where)
                        ]
                        if any(g.severity == "blocking" for g in c_gaps):
                            case_statuses.append("NEEDS_INFO")
                        elif any(g.type == "unsupported_flow" for g in c_gaps):
                            case_statuses.append("UNSUPPORTED")
                        else:
                            case_statuses.append("READY")

                    if not case_statuses:
                        case_statuses.append(determine_state(gaps, total_steps_or_cases=cases_count))

                    status_str = _format_status_counts(Counter(case_statuses))

                    rows.append(
                        EvaluationRow(
                            order=idx,
                            cases=str(cases_count),
                            exec_steps="-",
                            manual_steps="-",
                            gaps=gaps_str,
                            quote_pct="-",
                            status=status_str,
                        )
                    )

        except Exception:  # noqa: BLE001
            # Corrupt or unreadable document: Record ERROR row without halting evaluation
            rows.append(
                EvaluationRow(
                    order=idx,
                    cases="-",
                    exec_steps="-",
                    manual_steps="-",
                    gaps="-",
                    quote_pct="-",
                    status="ERROR",
                )
            )

    report_lines = [
        "# Evaluación de Normalización",
        "",
        "| # | Casos | Pasos ejecutables | Pasos manual | Faltantes (B/W/I) | % Citas válidas | Estado |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        report_lines.append(r.to_markdown())

    report_content = "\n".join(report_lines) + "\n"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_content, encoding="utf-8")

    return report_content


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for normalizer evaluation harness."""
    parser = argparse.ArgumentParser(description="Evaluate normalization metrics across document specifications.")
    parser.add_argument(
        "--docs",
        required=True,
        type=Path,
        help="Directory containing .docx and .pdf specification files",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build/eval.md"),
        help="Output markdown report path (default: build/eval.md)",
    )
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=Path("normalized"),
        help="Directory containing normalized JSON specifications (default: normalized/)",
    )

    args = parser.parse_args(argv)

    try:
        evaluate_documents(
            docs_dir=args.docs,
            out_path=args.out,
            normalized_dir=args.normalized_dir,
        )
        print(f"Evaluation report written to {args.out}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"Evaluation error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
