"""CLI tool to validate normalized QA specifications against schemas and grounding rules."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import requests
from pydantic import ValidationError

from normalizer.extract import extract_document
from normalizer.gaps import detect_gaps, determine_state
from normalizer.grounding import _extract_known_passwords
from normalizer.grounding import check as check_grounding
from normalizer.providers import get_provider
from normalizer.providers.masking import mask_dump_for_provider
from normalizer.render import render_case
from normalizer.schema import NormalizedDoc


def extract_file(doc_path: Path, out_dir: Path) -> int:
    """Extract content from document (.docx or .pdf) to JSON dump and images."""
    if not doc_path.exists():
        print(f"File not found: {doc_path}", file=sys.stderr)
        return 1

    try:
        extract_document(doc_path, out_dir)
        print(f"Extraction successful: {doc_path} -> {out_dir}")
        return 0
    except (ValueError, OSError) as e:
        print(f"Error extracting document: {e}", file=sys.stderr)
        return 1


def gaps_file(dump_path: Path) -> int:
    """Inspect specification gaps in extracted dump.json."""
    if not dump_path.exists():
        print(f"File not found: {dump_path}", file=sys.stderr)
        return 1

    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            dump_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: syntax error at line {e.lineno}, column {e.colno}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    gaps = detect_gaps(dump_data)
    if not gaps:
        print("No se detectaron faltantes.")
        return 0

    for gap in gaps:
        print(f"[{gap.severity.upper()}] tipo={gap.type} where={gap.where} ask={gap.ask}")

    return 0


def validate_file(json_path: Path, original_path: Path | None = None) -> int:
    """Validate a normalized JSON test specification."""
    if not json_path.exists():
        print(f"File not found: {json_path}", file=sys.stderr)
        return 1

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: syntax error at line {e.lineno}, column {e.colno}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # 1. Schema validation
    try:
        doc = NormalizedDoc.model_validate(raw_data)
    except ValidationError as ve:
        for err in ve.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            err_type = err.get("type", "schema_validation_error")
            # CRITICAL: Print only type and where, never input value or sensitive text
            print(f"VIOLATION: type={err_type} where={loc}", file=sys.stderr)
        return 1

    # 2. Grounding check
    dump_path = original_path
    if dump_path is None:
        candidates = [
            json_path.parent / "dump.json",
            Path("dump.json"),
            Path("build") / json_path.stem / "dump" / "dump.json",
            Path("build") / json_path.stem / "dump.json",
            Path("build/sample/dump/dump.json"),
            Path("build/sample/extracted/dump.json"),
        ]
        for cand in candidates:
            if cand.exists():
                dump_path = cand
                break

    if dump_path and dump_path.exists():
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                dump_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: syntax error at line {e.lineno}, column {e.colno}", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"Error reading dump JSON: {e}", file=sys.stderr)
            return 1

        violations = check_grounding(doc, dump_data)
        if violations:
            for v in violations:
                # CRITICAL: Print only type and where, never sensitive or offensive text
                print(f"VIOLATION: type={v.type} where={v.where}", file=sys.stderr)
            return 1

    print(f"Validation successful: {json_path}")
    return 0


def render_file(json_path: Path, out_dir: Path, original_path: Path | None = None) -> int:
    """Render canonical .docx and .gaps.md files from a normalized JSON file."""
    if not json_path.exists():
        print(f"File not found: {json_path}", file=sys.stderr)
        return 1

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: syntax error at line {e.lineno}, column {e.colno}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    try:
        doc = NormalizedDoc.model_validate(raw_data)
    except ValidationError as ve:
        for err in ve.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            err_type = err.get("type", "schema_validation_error")
            print(f"VIOLATION: type={err_type} where={loc}", file=sys.stderr)
        return 1

    dump_data = None
    dump_path = original_path
    if dump_path is None:
        candidates = [
            json_path.parent / "dump.json",
            Path("dump.json"),
            Path("build") / json_path.stem / "dump" / "dump.json",
            Path("build") / json_path.stem / "dump.json",
            Path("build/sample/dump/dump.json"),
            Path("build/sample/extracted/dump.json"),
        ]
        for cand in candidates:
            if cand.exists():
                dump_path = cand
                break

    if dump_path and dump_path.exists():
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                dump_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            dump_data = None

    out_dir.mkdir(parents=True, exist_ok=True)
    for case in doc.cases:
        known_pw = _extract_known_passwords(case, dump_data) if dump_data else None
        rendered_path = render_case(doc, case, out_dir, known_passwords=known_pw)
        print(f"Rendered: {rendered_path}")

    return 0


def normalize_document(
    doc_path: Path,
    provider_name: str = "agent_file",
    out_dir: Path = Path("normalized"),
    dry_run: bool = False,
    with_images: bool = False,
) -> int:
    """Execute end-to-end normalization pipeline: extract -> provide -> validate -> render."""
    if not doc_path.exists():
        print(f"File not found: {doc_path}", file=sys.stderr)
        return 1

    dump_dir = Path("build") / doc_path.stem / "dump"
    ext = doc_path.suffix.lower()

    if ext in [".docx", ".pdf"]:
        try:
            dump = extract_document(doc_path, dump_dir)
        except (ValueError, OSError) as e:
            print(f"Error extracting document: {e}", file=sys.stderr)
            return 1
    elif ext == ".json":
        try:
            with open(doc_path, "r", encoding="utf-8") as f:
                dump = json.load(f)
            dump_dir = doc_path.parent
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading dump JSON: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Unsupported file format: {ext}", file=sys.stderr)
        return 1

    img_dir = dump_dir / "img"
    images = list(img_dir.glob("*")) if img_dir.is_dir() else []

    masked_dump, _ = mask_dump_for_provider(dump)

    try:
        provider = get_provider(provider_name, stem=doc_path.stem)
    except ValueError as e:
        print(f"Provider error: {e}", file=sys.stderr)
        return 1

    doc_id = dump.get("meta", {}).get("identificador del caso") or doc_path.stem
    dry_run_path = Path("build") / str(doc_id) / "dry_run_payload.json"

    if dry_run:
        provider.normalize(
            dump=dump,
            images=images,
            with_images=with_images,
            dry_run=True,
            dry_run_path=dry_run_path,
        )
        print(f"Dry run complete. Payload written to {dry_run_path}")
        return 0

    try:
        normalized_data = provider.normalize(
            dump=dump,
            images=images,
            with_images=with_images,
            dry_run=False,
        )
    except (requests.RequestException, OSError, ValueError, RuntimeError, json.JSONDecodeError, TimeoutError, ConnectionError) as e:
        print(f"Provider error: {type(e).__name__}", file=sys.stderr)
        return 1

    try:
        doc = NormalizedDoc.model_validate(normalized_data)
    except ValidationError as ve:
        for err in ve.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            err_type = err.get("type", "schema_validation_error")
            print(f"VIOLATION: type={err_type} where={loc}", file=sys.stderr)
        return 1

    violations = check_grounding(doc, masked_dump)
    if violations:
        for v in violations:
            print(f"VIOLATION: type={v.type} where={v.where}", file=sys.stderr)
        return 1

    # Status check: NEEDS_INFO only if grounded but original document has blocking gaps
    original_gaps = detect_gaps(dump)
    has_blocking_gaps = any(g.severity == "blocking" for g in original_gaps)
    for case in doc.cases:
        if has_blocking_gaps:
            case.status = "NEEDS_INFO"
        elif not case.status or case.status == "NEEDS_INFO":
            case.status = determine_state(original_gaps, len(case.steps))

    out_dir.mkdir(parents=True, exist_ok=True)
    for case in doc.cases:
        known_pw = _extract_known_passwords(case, masked_dump)
        rendered_path = render_case(doc, case, out_dir, known_passwords=known_pw)
        print(f"Rendered: {rendered_path}")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint supporting extract, gaps, validate, render, and normalize subcommands."""
    parser = argparse.ArgumentParser(description="AI Test Normalizer CLI")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract", help="Extract document to JSON dump and images")
    extract_parser.add_argument("doc_path", type=Path, help="Path to input document (.docx or .pdf)")
    extract_parser.add_argument("--out", type=Path, default=Path("dump"), help="Destination directory for dump.json and images")

    gaps_parser = subparsers.add_parser("gaps", help="Scan dump.json for specification gaps")
    gaps_parser.add_argument("dump_path", type=Path, help="Path to dump.json file")

    validate_parser = subparsers.add_parser("validate", help="Validate normalized JSON file")
    validate_parser.add_argument("json_path", type=Path, help="Path to normalized JSON file")
    validate_parser.add_argument("--original", type=Path, default=None, help="Path to original dump.json file")

    render_parser = subparsers.add_parser("render", help="Render canonical docx and gaps reports")
    render_parser.add_argument("json_path", type=Path, help="Path to normalized JSON file")
    render_parser.add_argument("--out", type=Path, default=Path("normalized"), help="Output directory")
    render_parser.add_argument("--original", type=Path, default=None, help="Path to original dump.json file")

    normalize_parser = subparsers.add_parser("normalize", help="E2E normalize: extract, provide, validate, and render")
    normalize_parser.add_argument("doc_path", type=Path, help="Path to input document (.docx, .pdf, or dump.json)")
    normalize_parser.add_argument("--provider", choices=["agent_file", "api"], default="agent_file", help="Normalization provider")
    normalize_parser.add_argument("--out", type=Path, default=Path("normalized"), help="Output directory")
    normalize_parser.add_argument("--dry-run", action="store_true", default=False, help="Perform dry run without network or rendering")
    normalize_parser.add_argument("--with-images", action="store_true", default=False, help="Include screenshot images")

    args = parser.parse_args(argv)

    if args.command == "extract":
        return extract_file(args.doc_path, args.out)
    if args.command == "gaps":
        return gaps_file(args.dump_path)
    if args.command == "validate":
        return validate_file(args.json_path, args.original)
    if args.command == "render":
        return render_file(args.json_path, args.out, getattr(args, "original", None))
    if args.command == "normalize":
        return normalize_document(args.doc_path, args.provider, args.out, args.dry_run, args.with_images)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
