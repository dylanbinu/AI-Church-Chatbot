"""
Weekly / on-demand knowledge update for any registered church.

Flow: scrape site → ingest → validate → zip → upload S3 → invalidate chat Lambda
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import config
from data_sync import (
    build_bundle,
    head_remote_manifest,
    invalidate_chat_function,
    read_manifest,
    upload_bundle,
    write_manifest,
)
from ingest import ingest_records
from logging_config import setup_logging
from registry import UnknownChurchError, get_church
from webscrape import scrape_site

logger = setup_logging()


@dataclass
class UpdateResult:
    status: str
    church_id: str
    pages: int = 0
    chunks: int = 0
    uploaded: bool = False
    message: str = ""
    manifest: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _validate_bundle(
    church_id: str,
    runtime_dir: Path,
    pages: int,
    chunks: int,
    previous_pages: Optional[int],
) -> None:
    if pages < config.MIN_PAGES:
        raise RuntimeError(f"Gate failed: pages={pages} < MIN_PAGES={config.MIN_PAGES}")

    if previous_pages and previous_pages > 0:
        floor = int(previous_pages * config.REGRESSION_RATIO)
        if pages < floor:
            raise RuntimeError(
                f"Gate failed: pages={pages} regresses below {floor} "
                f"({config.REGRESSION_RATIO:.0%} of previous {previous_pages})"
            )

    if chunks <= 0:
        raise RuntimeError("Gate failed: no chunks produced")

    chroma_sqlite = runtime_dir / "chroma_db" / "chroma.sqlite3"
    if not chroma_sqlite.exists() or chroma_sqlite.stat().st_size < 100_000:
        # Fresh tiny DBs can be under 100KB for very small sites; only enforce if file missing
        if not chroma_sqlite.exists():
            raise RuntimeError("Gate failed: chroma.sqlite3 missing")

    # Smoke retrieval
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    db = Chroma(persist_directory=str(runtime_dir / "chroma_db"), embedding_function=embeddings)
    hits = db.similarity_search("service times", k=3, filter={"church_id": church_id})
    if not hits:
        raise RuntimeError("Gate failed: smoke similarity_search returned no hits")


def run_update(
    church_id: str,
    dry_run: bool = False,
    max_pages: Optional[int] = None,
) -> UpdateResult:
    try:
        church = get_church(church_id)
    except UnknownChurchError as e:
        return UpdateResult(status="Failed", church_id=church_id, error=str(e))

    config.require_openai_key()
    runtime_dir = config.church_runtime_dir(church_id)
    # Clean slate for this church runtime
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    previous = None
    if config.S3_BUCKET_NAME:
        previous = head_remote_manifest(config.S3_BUCKET_NAME, church_id)
    previous_pages = (previous or {}).get("pages")

    page_limit = max_pages or church.max_pages or config.MAX_PAGES
    data_path = config.data_file(church_id)

    logger.info(
        "update_start",
        extra={"extra_fields": {"church_id": church_id, "start_url": church.start_url, "max_pages": page_limit}},
    )

    try:
        records = scrape_site(church.start_url, output_file=data_path, max_pages=page_limit)
        ingest_result = ingest_records(
            church_id=church_id,
            input_file=data_path,
            reset=True,
            chroma_dir=config.chroma_path(church_id),
        )

        _validate_bundle(
            church_id=church_id,
            runtime_dir=runtime_dir,
            pages=ingest_result.pages,
            chunks=ingest_result.chunks,
            previous_pages=previous_pages,
        )

        manifest = write_manifest(
            church_id,
            runtime_dir,
            pages=ingest_result.pages,
            chunks=ingest_result.chunks,
            start_url=church.start_url,
            name=church.name,
        )

        if dry_run or not config.S3_BUCKET_NAME:
            zip_path = build_bundle(church_id, runtime_dir)
            msg = "Dry run complete" if dry_run else "Local bundle ready (no S3_BUCKET_NAME)"
            return UpdateResult(
                status="Success",
                church_id=church_id,
                pages=ingest_result.pages,
                chunks=ingest_result.chunks,
                uploaded=False,
                message=f"{msg}: {zip_path}",
                manifest=manifest,
            )

        zip_path = build_bundle(church_id, runtime_dir)
        upload_bundle(config.S3_BUCKET_NAME, church_id, zip_path, manifest)

        if config.CHAT_FUNCTION_NAME:
            invalidate_chat_function(config.CHAT_FUNCTION_NAME, manifest["built_at"])

        return UpdateResult(
            status="Success",
            church_id=church_id,
            pages=ingest_result.pages,
            chunks=ingest_result.chunks,
            uploaded=True,
            message="Bundle uploaded",
            manifest=manifest,
        )
    except Exception as e:
        logger.exception("update_failed", extra={"extra_fields": {"church_id": church_id}})
        return UpdateResult(status="Failed", church_id=church_id, error=str(e))


def handler(event, context):
    """Lambda entrypoint for EventBridge Scheduler."""
    church_id = config.DEFAULT_CHURCH_ID
    dry_run = False
    max_pages = None

    if isinstance(event, dict):
        church_id = event.get("church_id") or church_id
        dry_run = bool(event.get("dry_run"))
        if event.get("max_pages") is not None:
            max_pages = int(event["max_pages"])

    result = run_update(church_id=church_id, dry_run=dry_run, max_pages=max_pages)
    payload = asdict(result)
    # Lambda should fail the invocation on update failure so Scheduler retries
    if result.status != "Success":
        raise RuntimeError(result.error or "Update failed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/publish a church knowledge bundle")
    parser.add_argument("--church_id", default=config.DEFAULT_CHURCH_ID)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max_pages", type=int, default=None)
    args = parser.parse_args()

    result = run_update(args.church_id, dry_run=args.dry_run, max_pages=args.max_pages)
    print(result)
    if result.status != "Success":
        sys.exit(1)


if __name__ == "__main__":
    main()
