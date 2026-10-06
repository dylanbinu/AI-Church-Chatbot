"""
Multi-tenant Church Chatbot API.

One application serves every registered church. Per-request `church_id`
selects the scraped knowledge bundle (local `.runtime/` or S3 zip).
"""
from __future__ import annotations

import re
import threading
import time
import traceback
from typing import List, Optional, Tuple

# pysqlite3 shim for Lambda Chromadb
try:
    __import__("pysqlite3")
    import sys as _sys

    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except ImportError:
    pass

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

import config
from app_state import get_state, reload_state
from auth import require_api_key
from data_sync import head_remote_manifest
from link_utils import validate_and_fix_links
from logging_config import setup_logging
from registry import UnknownChurchError, all_allowed_origins, get_church, list_church_ids
from retrieval import CONTEXT_CHAR_LIMIT, build_search_query, retrieve_and_rank

logger = setup_logging()

CACHE_TTL_SECONDS = 600
CACHE_MAX = 128
_cache_lock = threading.Lock()
_answer_cache: dict[Tuple[str, str, str, str], Tuple[float, "ChatResponse"]] = {}


def normalize_question(text: str) -> str:
    return " ".join(text.lower().split()).strip(" ?.!")


def answer_cache_key(church_id: str, data_version: str, built_at: str, message: str, history: List) -> Optional[Tuple[str, str, str, str]]:
    """Cache standalone questions. Follow-ups depend on history and stay uncached."""
    if history:
        return None
    normalized = normalize_question(message)
    if not normalized:
        return None
    return (church_id, data_version, built_at or "", normalized)


def get_cached_answer(key: Tuple[str, str, str, str]) -> Optional["ChatResponse"]:
    now = time.monotonic()
    with _cache_lock:
        hit = _answer_cache.get(key)
        if not hit:
            return None
        expires_at, response = hit
        if expires_at <= now:
            _answer_cache.pop(key, None)
            return None
        return response.model_copy()


def store_cached_answer(key: Tuple[str, str, str, str], response: "ChatResponse") -> None:
    now = time.monotonic()
    with _cache_lock:
        expired = [existing for existing, (expires_at, _) in _answer_cache.items() if expires_at <= now]
        for existing in expired:
            _answer_cache.pop(existing, None)
        _answer_cache[key] = (now + CACHE_TTL_SECONDS, response.model_copy())
        overflow = len(_answer_cache) - CACHE_MAX
        if overflow > 0:
            oldest = sorted(_answer_cache.items(), key=lambda item: item[1][0])[:overflow]
            for old_key, _ in oldest:
                _answer_cache.pop(old_key, None)


def clear_answer_cache() -> None:
    with _cache_lock:
        _answer_cache.clear()


class ChatMessage(BaseModel):
    role: str
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatMessage] = Field(default_factory=list, max_length=20)
    church_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    church_id: str


def _cors_origins() -> List[str]:
    if config.ALLOWED_ORIGINS_ENV:
        return config.ALLOWED_ORIGINS_ENV
    origins = all_allowed_origins()
    origins.extend(
        [
            "http://localhost:8004",
            "http://127.0.0.1:8004",
            "http://localhost:3000",
            "null",
        ]
    )
    seen = set()
    out = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


def create_app() -> FastAPI:
    app = FastAPI(
        title="Church Assistant API",
        docs_url=None if config.IS_LAMBDA else "/docs",
        redoc_url=None if config.IS_LAMBDA else "/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = request.headers.get("x-amzn-requestid") or request.headers.get("x-request-id")
        logger.error(
            "unhandled_error",
            extra={"extra_fields": {"path": str(request.url.path), "error": str(exc), "request_id": request_id}},
        )
        logger.debug(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal server error",
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request",
                    "details": exc.errors(),
                }
            },
        )

    @app.get("/health")
    async def health(church_id: Optional[str] = None):
        cid = church_id or config.DEFAULT_CHURCH_ID
        try:
            state = get_state(cid)
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "church_id": cid,
                    "ready": False,
                    "error": str(e),
                },
            )

        remote = None
        stale = False
        if config.S3_BUCKET_NAME:
            remote = head_remote_manifest(config.S3_BUCKET_NAME, cid)
            local_built = (state.manifest or {}).get("built_at")
            remote_built = (remote or {}).get("built_at")
            stale = bool(remote_built and local_built and remote_built != local_built)

        return {
            "status": "ok" if not stale else "stale",
            "ready": True,
            "church_id": cid,
            "church_name": state.church.name,
            "pages": state.context.page_count,
            "manifest": state.manifest,
            "remote_manifest": remote,
            "stale": stale,
            "data_version": config.DATA_VERSION,
            "registered_churches": list_church_ids(),
        }

    @app.get("/churches")
    async def churches():
        return {
            "churches": [
                {
                    "id": cid,
                    "name": get_church(cid).name,
                    "domain": get_church(cid).domain,
                }
                for cid in list_church_ids()
            ]
        }

    @app.post("/admin/reload", dependencies=[Depends(require_api_key)])
    async def admin_reload(church_id: Optional[str] = None):
        if not config.API_KEYS and config.IS_LAMBDA:
            raise HTTPException(status_code=401, detail="API_KEYS must be configured for admin endpoints")
        cid = church_id or config.DEFAULT_CHURCH_ID
        state = reload_state(cid)
        return {
            "status": "reloaded",
            "church_id": cid,
            "pages": state.context.page_count,
            "manifest": state.manifest,
        }

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
    async def chat(request: ChatRequest):
        church_id = request.church_id or config.DEFAULT_CHURCH_ID
        try:
            get_church(church_id)
        except UnknownChurchError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        try:
            state = get_state(church_id)
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            logger.exception("state_load_failed", extra={"extra_fields": {"church_id": church_id}})
            raise HTTPException(status_code=503, detail="Knowledge base unavailable") from e

        recent_history = request.history[-8:]
        built_at = str((state.manifest or {}).get("built_at") or "")
        cache_key = answer_cache_key(
            church_id,
            config.DATA_VERSION,
            built_at,
            request.message,
            recent_history,
        )
        if cache_key:
            cached = get_cached_answer(cache_key)
            if cached is not None:
                logger.info("chat_cache_hit", extra={"extra_fields": {"church_id": church_id}})
                return cached

        langchain_history = [
            HumanMessage(content=msg.content) if msg.role == "user" else AIMessage(content=msg.content)
            for msg in recent_history
        ]

        final_docs = retrieve_and_rank(
            build_search_query(request.message, recent_history),
            state.vector_db,
            state.valid_urls,
            state.preferred_keyword,
            church_id,
            state.church.retrieval,
        )

        parts = []
        total = 0
        for d in final_docs:
            block = f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
            if total + len(block) > CONTEXT_CHAR_LIMIT:
                break
            parts.append(block)
            total += len(block)
        context_text = "\n\n".join(parts)

        contact_url = state.main_domain or f"https://{state.church.domain}"
        for u in state.valid_urls:
            if "/contact" in u or "/connect" in u:
                contact_url = u
                break

        if not context_text:
            empty = ChatResponse(
                response=(
                    f"I apologize, that specific detail isn't available right now. "
                    f"Please visit our [Contact Page]({contact_url})."
                ),
                sources=[],
                church_id=church_id,
            )
            if cache_key:
                store_cached_answer(cache_key, empty)
            return empty

        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a warm, welcoming, and helpful digital greeter for {church_name}.

1. **Persona:** Be a warm, friendly church assistant. ALWAYS start with a conversational sentence.
2. **Strict Accuracy:** Answer **ONLY** using the provided `Context`.
    - **NO Outside Knowledge:** Do not answer general questions (e.g. theology, biology) not in text.
    - **Missing Info:** If answer is not in context, say: "I'm not sure about that specific detail based on our website, but I'd love to help!" and link to **[Contact Page]({{CONTACT_URL}})**.
    - **Links:** Use **ONLY** URLs from `Context`. Never invent URLs.
3. **Formatting (Cards):**
    - Use bullet points with links for lists: `* **[Campus Name](url)**`
    - Deduplicate links: Merge multiple topics (groups, serve) into one bullet if they share a URL.
4. **Service Times:**
    - Use only the days and clock times written on that campus's own page in the Context.
    - Keep campuses separate. Never copy one campus's times onto another.
    - Times under "join us online" or "watch online" are online only. Do not attach them to a campus.
    - Include Saturday when that campus page lists Saturday.
    - If a campus is named but its own page is not in the Context, say you do not have that campus's times. Do not guess a schedule.
5. **Giving:**
    - **Methods Only:** List giving methods: Online, Text, Mail, In-Person.
    - **Do NOT list campuses** as giving options unless identifying a physical drop-off.
    - **No "Online Campus":** Never invent an "Online Campus" entity.
6. **Fallbacks:**
    - If a specific page is missing, link to **Home Page** or **Contact Page**.
    - Link text must match page titles in context.
Context: {context}
""",
                ),
                *langchain_history,
                ("human", "{question}"),
            ]
        )

        chain = prompt_template | state.llm
        response = chain.invoke(
            {
                "context": context_text,
                "question": request.message,
                "church_name": state.church.name,
            }
        )

        content = response.content if hasattr(response, "content") else str(response)
        pattern = r"(?:\{+\s*CONTACT_URL\s*\}+|%7B\s*CONTACT_URL\s*%7D)"
        content = re.sub(pattern, contact_url, content, flags=re.IGNORECASE)
        validated = validate_and_fix_links(content, state.valid_urls, contact_url, state.main_domain)
        unique_sources = list({d.metadata.get("source", "") for d in final_docs if d.metadata.get("source")})

        result = ChatResponse(response=validated, sources=unique_sources, church_id=church_id)
        if cache_key:
            store_cached_answer(cache_key, result)
        return result

    @app.get("/church_chatbot.js")
    async def get_widget_js():
        path = config.BASE_DIR / "church_chatbot.js"
        return FileResponse(path, media_type="application/javascript")

    @app.get("/", response_class=HTMLResponse)
    async def get_widget():
        widget_path = config.BASE_DIR / "widget_demo.html"
        return widget_path.read_text(encoding="utf-8")

    return app


app = create_app()
_mangum_handler = None


def handler(event, context):
    """Chat Lambda entrypoint (slim image — no scrape/updater imports)."""
    global _mangum_handler
    if _mangum_handler is None:
        from mangum import Mangum

        _mangum_handler = Mangum(app)
    return _mangum_handler(event, context)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=config.PORT, reload=False)
