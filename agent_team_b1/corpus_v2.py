"""发现 A 榜索引未覆盖、但 B 榜原始目录已提供的官方文档。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUFFIXES = {".pdf", ".html", ".txt"}


@dataclass(frozen=True)
class MissingDocument:
    domain: str
    doc_id: str
    path: Path


def discover_missing_documents(
    raw_root: Path,
    documents_path: Path,
    *,
    domains: tuple[str, ...],
) -> list[MissingDocument]:
    """按 `(domain, stem)` 比较原始文件和已有 documents.jsonl。"""
    indexed: set[tuple[str, str]] = set()
    for line in Path(documents_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        indexed.add((str(row.get("domain", "")), str(row.get("doc_id", ""))))

    missing: list[MissingDocument] = []
    for domain in domains:
        domain_root = Path(raw_root) / domain
        if not domain_root.exists():
            raise FileNotFoundError(f"原始领域目录不存在: {domain_root}")
        for path in sorted(domain_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            key = (domain, path.stem)
            if key in indexed:
                continue
            missing.append(MissingDocument(domain=domain, doc_id=path.stem, path=path))
    return sorted(missing, key=lambda item: (item.domain, item.doc_id))
