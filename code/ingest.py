"""Ingest scraped JSONL into a per-church Chroma vector store."""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from context_manager import is_useful_page
from logging_config import setup_logging

logger = setup_logging()


@dataclass
class IngestResult:
    church_id: str
    pages: int
    chunks: int
    chroma_path: str


def _load_documents(data_path: Path, church_id: str) -> List[Document]:
    documents: List[Document] = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = data.get("source") or data.get("url")
            content = data.get("content") or data.get("text") or ""
            if not src or not is_useful_page(content):
                continue
            documents.append(
                Document(
                    page_content=content,
                    metadata={"source": src, "church_id": church_id},
                )
            )
    return documents


def ingest_records(
    church_id: str,
    input_file: str | Path,
    reset: bool = False,
    chroma_dir: Optional[str | Path] = None,
) -> IngestResult:
    config.require_openai_key()
    data_path = Path(input_file)
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    persist_dir = Path(chroma_dir) if chroma_dir else config.chroma_path(church_id)
    persist_dir.parent.mkdir(parents=True, exist_ok=True)

    if reset and persist_dir.exists():
        shutil.rmtree(persist_dir)
        logger.info("chroma_reset", extra={"extra_fields": {"path": str(persist_dir)}})

    persist_dir.mkdir(parents=True, exist_ok=True)

    embedding_model = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    db = Chroma(persist_directory=str(persist_dir), embedding_function=embedding_model)

    if not reset:
        try:
            existing = db.get(where={"church_id": church_id})
            ids = (existing or {}).get("ids") or []
            if ids:
                db.delete(ids=ids)
                logger.info(
                    "chroma_church_cleared",
                    extra={"extra_fields": {"church_id": church_id, "deleted": len(ids)}},
                )
        except Exception as e:
            logger.warning("chroma_cleanup_failed", extra={"extra_fields": {"error": str(e)}})

    documents = _load_documents(data_path, church_id)
    if not documents:
        raise RuntimeError(f"No useful pages to ingest from {data_path}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        separators=["\n\n", "\n", "###", "##", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        db.add_documents(batch)
        logger.info(
            "ingest_batch",
            extra={"extra_fields": {"batch": i // batch_size + 1, "size": len(batch)}},
        )

    result = IngestResult(
        church_id=church_id,
        pages=len(documents),
        chunks=len(chunks),
        chroma_path=str(persist_dir),
    )
    logger.info(
        "ingest_complete",
        extra={"extra_fields": {"church_id": church_id, "pages": result.pages, "chunks": result.chunks}},
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest church JSONL into Chroma")
    parser.add_argument("--church_id", type=str, default=config.DEFAULT_CHURCH_ID)
    parser.add_argument("--input_file", type=str, default="scraped_data.jsonl")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    data_path = Path(args.input_file)
    if not data_path.is_absolute():
        if data_path.exists():
            data_path = data_path.resolve()
        else:
            candidate = config.PROJECT_ROOT / args.input_file
            data_path = candidate if candidate.exists() else data_path

    try:
        result = ingest_records(args.church_id, data_path, reset=args.reset)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingested {result.pages} pages / {result.chunks} chunks for {result.church_id}")


if __name__ == "__main__":
    main()
