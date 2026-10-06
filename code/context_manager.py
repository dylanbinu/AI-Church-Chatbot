"""Build URL context used for link validation and retrieval boosts."""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Set
from urllib.parse import urlparse

from logging_config import setup_logging

logger = setup_logging()


@dataclass
class ChurchContext:
    valid_urls: Set[str]
    main_domain: str
    preferred_keyword: Optional[str] = None
    page_count: int = 0


def is_useful_page(content: str, min_chars: int = 40) -> bool:
    if not content or len(content.strip()) < min_chars:
        return False
    lower = content.lower()
    if "page not found" in lower or "404" in lower:
        return False
    if "this page doesn't exist" in lower or "this page does not exist" in lower:
        return False
    return True


def build_context(
    records: Iterable[dict],
    preferred_keyword: Optional[str] = None,
) -> ChurchContext:
    valid_urls: Set[str] = set()
    skipped = 0

    for data in records:
        url = (data.get("source") or data.get("url") or "").strip()
        content = data.get("content") or data.get("text") or ""
        if not url:
            skipped += 1
            continue
        if not is_useful_page(content):
            skipped += 1
            continue
        valid_urls.add(url.rstrip("/"))

    main_domain = ""
    if valid_urls:
        domains = [urlparse(u).netloc for u in valid_urls if urlparse(u).netloc]
        common = Counter(domains).most_common(1)
        if common:
            main_domain = f"https://{common[0][0]}"

    if skipped:
        logger.info("context_build_skipped_pages", extra={"extra_fields": {"skipped": skipped}})

    return ChurchContext(
        valid_urls=valid_urls,
        main_domain=main_domain,
        preferred_keyword=preferred_keyword,
        page_count=len(valid_urls),
    )


def load_context_from_file(
    filepath: str | Path,
    preferred_keyword: Optional[str] = None,
) -> Optional[ChurchContext]:
    path = Path(filepath)
    if not path.exists():
        return None

    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return build_context(records, preferred_keyword=preferred_keyword)
    except OSError as e:
        logger.error("context_load_failed", extra={"extra_fields": {"path": str(path), "error": str(e)}})
        return None
