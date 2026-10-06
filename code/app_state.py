"""Per-church runtime state — one chatbot app, many church data bundles."""
from __future__ import annotations

import logging
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set
from urllib.parse import urlparse

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import config
from context_manager import ChurchContext, load_context_from_file
from data_sync import download_bundle, read_manifest
from logging_config import setup_logging
from registry import ChurchConfig, get_church

logger = setup_logging()


@dataclass
class AppState:
    church_id: str
    church: ChurchConfig
    context: ChurchContext
    vector_db: Chroma
    embedding_model: OpenAIEmbeddings
    llm: ChatOpenAI
    manifest: Optional[dict] = None
    loaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data_version: str = "0"

    @property
    def valid_urls(self) -> Set[str]:
        return self.context.valid_urls

    @property
    def main_domain(self) -> str:
        return self.context.main_domain

    @property
    def preferred_keyword(self) -> Optional[str]:
        return self.context.preferred_keyword or self.church.preferred_keyword


_lock = threading.Lock()
_states: Dict[str, AppState] = {}
_shared_embeddings: Optional[OpenAIEmbeddings] = None
_shared_llm: Optional[ChatOpenAI] = None


def _get_shared_models() -> tuple[OpenAIEmbeddings, ChatOpenAI]:
    global _shared_embeddings, _shared_llm
    config.require_openai_key()
    if _shared_embeddings is None:
        _shared_embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME)
    if _shared_llm is None:
        _shared_llm = ChatOpenAI(
            model=config.LLM_MODEL_NAME,
            temperature=config.LLM_TEMPERATURE,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )
    return _shared_embeddings, _shared_llm


def _context_from_vector_db(
    vector_db: Chroma,
    church: ChurchConfig,
) -> ChurchContext:
    """Rebuild URL context from Chroma metadata (legacy chroma-only S3 zips)."""
    valid_urls: Set[str] = set()
    try:
        raw = vector_db.get(include=["metadatas"])
        for meta in raw.get("metadatas") or []:
            if not meta:
                continue
            src = (meta.get("source") or "").rstrip("/")
            if src:
                valid_urls.add(src)
    except Exception as e:
        logger.warning(
            "chroma_url_extract_failed",
            extra={"extra_fields": {"error": str(e)}},
        )

    main_domain = f"https://{church.domain}" if church.domain else ""
    if valid_urls:
        domains = [urlparse(u).netloc for u in valid_urls if urlparse(u).netloc]
        common = Counter(domains).most_common(1)
        if common:
            main_domain = f"https://{common[0][0]}"

    return ChurchContext(
        valid_urls=valid_urls,
        main_domain=main_domain,
        preferred_keyword=church.preferred_keyword,
        page_count=len(valid_urls),
    )


def _ensure_local_bundle(church_id: str, force_download: bool = False) -> Path:
    """Download from S3 when configured; otherwise expect a local .runtime bundle."""
    dest = config.church_runtime_dir(church_id)
    chroma = config.chroma_path(church_id)

    if config.S3_BUCKET_NAME:
        needs_download = force_download or not chroma.exists()
        if needs_download:
            download_bundle(config.S3_BUCKET_NAME, church_id, dest)
        if not config.chroma_path(church_id).exists():
            raise FileNotFoundError(
                f"S3 bundle for '{church_id}' did not contain chroma_db after extract."
            )
        return dest

    if not chroma.exists():
        raise FileNotFoundError(
            f"No local bundle for '{church_id}' at {dest}. "
            f"Run: python updater.py --church_id {church_id}"
        )
    return dest


def load_state(church_id: str, force: bool = False) -> AppState:
    with _lock:
        existing = _states.get(church_id)
        version_changed = bool(existing and existing.data_version != config.DATA_VERSION)
        if existing and not force and not version_changed:
            return existing

        church = get_church(church_id)
        runtime_dir = _ensure_local_bundle(
            church_id,
            force_download=force or version_changed,
        )
        embeddings, llm = _get_shared_models()

        chroma_dir = str(config.chroma_path(church_id))
        vector_db = Chroma(persist_directory=chroma_dir, embedding_function=embeddings)

        ctx = load_context_from_file(
            config.data_file(church_id),
            preferred_keyword=church.preferred_keyword,
        )
        if ctx is None or not ctx.valid_urls:
            ctx = _context_from_vector_db(vector_db, church)

        manifest = read_manifest(config.manifest_path(church_id))
        if manifest is None:
            manifest = {
                "church_id": church_id,
                "built_at": "legacy-bundle",
                "pages": ctx.page_count,
                "note": "chroma_only_legacy_zip",
            }

        state = AppState(
            church_id=church_id,
            church=church,
            context=ctx,
            vector_db=vector_db,
            embedding_model=embeddings,
            llm=llm,
            manifest=manifest,
            data_version=config.DATA_VERSION,
        )
        _states[church_id] = state
        logger.info(
            "state_loaded",
            extra={
                "extra_fields": {
                    "church_id": church_id,
                    "pages": ctx.page_count,
                    "runtime_dir": str(runtime_dir),
                    "data_version": config.DATA_VERSION,
                }
            },
        )
        return state


def get_state(church_id: Optional[str] = None) -> AppState:
    cid = church_id or config.DEFAULT_CHURCH_ID
    return load_state(cid, force=False)


def reload_state(church_id: str) -> AppState:
    if config.S3_BUCKET_NAME:
        dest = config.church_runtime_dir(church_id)
        download_bundle(config.S3_BUCKET_NAME, church_id, dest)
    return load_state(church_id, force=True)


def clear_states() -> None:
    with _lock:
        _states.clear()
