"""Extract raw text paragraphs, table metadata, and images from .docx and .pdf specifications."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import docx
import pypdf

from parsers.docx_parser import DocxParser

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
CASE_PATTERN = re.compile(r"^Caso\s*#?\s*(\d+)[:.]?\s*(.*)$", re.IGNORECASE)


def _extract_docx(doc_path: Path, out_dir: Path) -> dict[str, Any]:
    """Extract content from a Microsoft Word (.docx) document."""
    doc = docx.Document(str(doc_path))
    meta = DocxParser._extract_table_data(doc)

    img_dir = out_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    img_counter = 1
    paragraphs_data: list[dict[str, Any]] = []

    for p in doc.paragraphs:
        r_ids: list[str] = p._p.xpath(".//a:blip/@r:embed")
        p_images: list[str] = []

        seen_r_ids: set[str] = set()
        for r_id in r_ids:
            if r_id in seen_r_ids:
                continue
            seen_r_ids.add(r_id)

            if r_id in p.part.related_parts:
                part = p.part.related_parts[r_id]
                if hasattr(part, "image"):
                    ext = getattr(part.image, "ext", "png") or "png"
                    img_filename = f"image{img_counter}.{ext}"
                    img_counter += 1
                    img_rel = f"img/{img_filename}"
                    (img_dir / img_filename).write_bytes(part.image.blob)
                    p_images.append(img_rel)

        text = p.text.strip()
        if text:
            line_num = len(paragraphs_data) + 1
            paragraphs_data.append({
                "line": line_num,
                "text": text,
                "images": p_images,
            })
        elif p_images:
            # Screenshot paragraph without text: anchor to closest preceding text line
            if paragraphs_data:
                paragraphs_data[-1]["images"].extend(p_images)
            else:
                paragraphs_data.append({
                    "line": 1,
                    "text": "",
                    "images": p_images,
                })

    # Detect test cases
    case_starts: list[tuple[int, str, int]] = []
    for p_data in paragraphs_data:
        m = CASE_PATTERN.match(p_data["text"])
        if m:
            n = int(m.group(1))
            raw_title = m.group(2).strip()
            title = raw_title if raw_title else p_data["text"].strip()
            case_starts.append((n, title, p_data["line"]))

    cases: list[dict[str, Any]] = []
    if case_starts:
        for idx, (n, title, start_line) in enumerate(case_starts):
            if idx + 1 < len(case_starts):
                end_line = case_starts[idx + 1][2] - 1
            else:
                end_line = len(paragraphs_data)
            cases.append({
                "n": n,
                "title": title,
                "start_line": start_line,
                "end_line": max(start_line, end_line),
            })
    else:
        fallback_title = (
            meta.get("descripción completa")
            or meta.get("descripción corta")
            or meta.get("descripcion completa")
            or meta.get("descripcion corta")
            or doc_path.stem
        )
        end_line = len(paragraphs_data) if paragraphs_data else 1
        cases.append({
            "n": 1,
            "title": fallback_title,
            "start_line": 1,
            "end_line": max(1, end_line),
        })

    # Detect URLs
    found_links: list[str] = []
    for val in meta.values():
        if isinstance(val, str):
            found_links.extend(URL_PATTERN.findall(val))
    for p_data in paragraphs_data:
        found_links.extend(URL_PATTERN.findall(p_data["text"]))

    links = list(dict.fromkeys(found_links))

    return {
        "meta": meta,
        "paragraphs": paragraphs_data,
        "cases": cases,
        "links": links,
    }


def _extract_pdf(doc_path: Path, out_dir: Path) -> dict[str, Any]:
    """Extract content from a PDF document.

    Extracts text paragraphs and links. Attempts to extract embedded page images
    if present; if image extraction is not supported for specific formats,
    continues with text-only extraction.
    """
    reader = pypdf.PdfReader(str(doc_path))
    meta: dict[str, str] = {}
    if reader.metadata:
        for k, v in reader.metadata.items():
            if v:
                meta[str(k).strip("/").lower()] = str(v)

    img_dir = out_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    img_counter = 1
    paragraphs_data: list[dict[str, Any]] = []

    for page in reader.pages:
        page_images: list[str] = []
        try:
            for img_file in getattr(page, "images", []):
                ext = Path(img_file.name).suffix.lstrip(".") or "png"
                img_filename = f"image{img_counter}.{ext}"
                img_counter += 1
                (img_dir / img_filename).write_bytes(img_file.data)
                page_images.append(f"img/{img_filename}")
        except (KeyError, ValueError, TypeError, AttributeError, OSError):
            # Fallback documented: text-only if image extraction fails
            page_images = []

        raw_text = page.extract_text() or ""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for line in lines:
            line_num = len(paragraphs_data) + 1
            paragraphs_data.append({
                "line": line_num,
                "text": line,
                "images": [],
            })
        if page_images and paragraphs_data:
            paragraphs_data[-1]["images"].extend(page_images)

    case_starts: list[tuple[int, str, int]] = []
    for p in paragraphs_data:
        m = CASE_PATTERN.match(p["text"])
        if m:
            n = int(m.group(1))
            raw_title = m.group(2).strip()
            title = raw_title if raw_title else p["text"].strip()
            case_starts.append((n, title, p["line"]))

    cases: list[dict[str, Any]] = []
    if case_starts:
        for idx, (n, title, start_line) in enumerate(case_starts):
            if idx + 1 < len(case_starts):
                end_line = case_starts[idx + 1][2] - 1
            else:
                end_line = len(paragraphs_data)
            cases.append({
                "n": n,
                "title": title,
                "start_line": start_line,
                "end_line": max(start_line, end_line),
            })
    else:
        fallback_title = meta.get("title") or doc_path.stem
        end_line = len(paragraphs_data) if paragraphs_data else 1
        cases.append({
            "n": 1,
            "title": fallback_title,
            "start_line": 1,
            "end_line": max(1, end_line),
        })

    found_links: list[str] = []
    for val in meta.values():
        found_links.extend(URL_PATTERN.findall(val))
    for p in paragraphs_data:
        found_links.extend(URL_PATTERN.findall(p["text"]))

    links = list(dict.fromkeys(found_links))

    return {
        "meta": meta,
        "paragraphs": paragraphs_data,
        "cases": cases,
        "links": links,
    }


def extract_document(doc_path: Path | str, out_dir: Path | str) -> dict[str, Any]:
    """Extract metadata, text paragraphs, cases, and images from .docx or .pdf."""
    path = Path(doc_path)
    output_dir = Path(out_dir)

    if not path.exists():
        raise FileNotFoundError(f"Document file not found: {path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    ext = path.suffix.lower()
    if ext == ".docx":
        dump = _extract_docx(path, output_dir)
    elif ext == ".pdf":
        dump = _extract_pdf(path, output_dir)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .docx and .pdf are supported.")

    dump_file = output_dir / "dump.json"
    with open(dump_file, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2, ensure_ascii=False)

    return dump


def main() -> None:
    """CLI entry point for extracting document content."""
    parser = argparse.ArgumentParser(description="Extract unstructured .docx/.pdf to JSON dump and images.")
    parser.add_argument("document", type=Path, help="Path to input .docx or .pdf file")
    parser.add_argument("--out", required=True, type=Path, help="Destination directory for dump.json and images")

    args = parser.parse_args()
    extract_document(args.document, args.out)


if __name__ == "__main__":
    main()
