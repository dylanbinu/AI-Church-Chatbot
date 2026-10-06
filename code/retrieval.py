"""Hybrid retrieval: one embedding, intent page injection, blended ranking."""
from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from langchain_core.documents import Document

RESULT_LIMIT = 6
SEMANTIC_K = 20
CONTEXT_CHAR_LIMIT = 8000
FORCED_RELEVANCE = 0.70

HIGH_VALUE_BONUS = 0.12
LOW_VALUE_PENALTY = 0.28
PREFERRED_BONUS = 0.05
CAMPUS_BONUS = 0.40
ROOT_BONUS = 0.20
_TIME_TEXT = re.compile(
    r"\b(?:sun|mon|tues|wednes|thurs|fri|satur)day\b|\b\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)


def build_search_query(message: str, history: Sequence[Any]) -> str:
    """Search with the previous visitor question so follow-ups keep their topic."""
    previous = ""
    for msg in reversed(list(history)):
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None)
        if role is None and isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
        if role == "user" and isinstance(content, str) and content.strip():
            previous = content.strip()
            break
    current = message.strip()
    if previous and previous.lower() != current.lower():
        return f"{previous}\n{current}"
    return current


def _intent_matches(query: str, intent: Any) -> bool:
    if intent.any_terms and any(term in query for term in intent.any_terms):
        return True
    if intent.all_terms and all(term in query for term in intent.all_terms):
        return True
    return False


def urls_for_intent(valid_urls: Set[str], intent: Any) -> List[str]:
    matched: List[str] = []
    for url in valid_urls:
        lower = url.lower()
        if any(path in lower for path in intent.paths):
            matched.append(url)
            continue
        if intent.include_site_root and url.rstrip("/").count("/") == 2:
            matched.append(url)
    if getattr(intent, "prefer_specific", False):
        matched.sort(key=_location_specificity, reverse=True)
    else:
        matched.sort(key=len)
    return matched[: max(intent.limit, 0)]


def _location_specificity(url: str) -> Tuple[int, int]:
    """Campus pages outrank the short locations index."""
    parts = [part for part in urlparse(url).path.split("/") if part]
    campus_page = 1 if len(parts) >= 2 and parts[0] in ("locations", "campuses") else 0
    return (campus_page, len(parts))


def _documents_for_church(vector_db: Any, church_id: Optional[str]) -> List[Document]:
    where = {"church_id": church_id} if church_id else None
    raw = vector_db.get(where=where, include=["documents", "metadatas"])
    documents = (raw or {}).get("documents") or []
    metadatas = (raw or {}).get("metadatas") or []
    docs: List[Document] = []
    for text, meta in zip(documents, metadatas):
        if not text:
            continue
        docs.append(Document(page_content=text, metadata=dict(meta or {})))
    return docs


def _wants_service_times(query: str) -> bool:
    lowered = query.lower()
    return any(word in lowered for word in ("time", "service", "sunday", "saturday", "when"))


def _best_chunk_per_url(
    docs: Sequence[Document],
    urls: Sequence[str],
    query: str = "",
) -> List[Document]:
    wanted = {url.rstrip("/") for url in urls}
    prefer_times = _wants_service_times(query)
    chosen = {}
    for doc in docs:
        source = (doc.metadata.get("source") or "").rstrip("/")
        if source not in wanted:
            continue
        current = chosen.get(source)
        if current is None or _chunk_rank(doc, prefer_times) > _chunk_rank(current, prefer_times):
            chosen[source] = doc
    return list(chosen.values())


def _chunk_rank(doc: Document, prefer_times: bool) -> Tuple[int, int]:
    hits = len(_TIME_TEXT.findall(doc.page_content)) if prefer_times else 0
    return (hits, len(doc.page_content))


def url_adjustment(
    source: str,
    query: str,
    valid_urls: Set[str],
    preferred_campus_keyword: Optional[str],
    profile: Any,
) -> float:
    lowered = source.lower()
    score = 0.0
    if any(sub in lowered for sub in profile.high_value):
        score += HIGH_VALUE_BONUS
    if any(sub in lowered for sub in profile.low_value):
        score -= LOW_VALUE_PENALTY
    if preferred_campus_keyword and preferred_campus_keyword.lower() in lowered:
        score += PREFERRED_BONUS

    normalized_query = query.lower().replace(" ", "-")
    for url in valid_urls:
        slug = url.rstrip("/").split("/")[-1].lower()
        if slug and slug in normalized_query and slug in lowered:
            score += CAMPUS_BONUS
            break

    if lowered.rstrip("/").count("/") == 2:
        score += ROOT_BONUS
    return score


def _signature(doc: Document) -> Tuple[str, str]:
    return (doc.metadata.get("source", ""), doc.page_content[:100])


def retrieve_and_rank(
    query: str,
    vector_db: Any,
    valid_urls: Set[str],
    preferred_campus_keyword: Optional[str] = None,
    church_id: Optional[str] = None,
    profile: Any = None,
) -> List[Document]:
    """Embed the question once, inject intent pages from metadata, blend scores."""
    if profile is None:
        from registry import DEFAULT_RETRIEVAL

        profile = DEFAULT_RETRIEVAL

    q = query.lower()
    forced_urls: List[str] = []
    for intent in profile.intents:
        if _intent_matches(q, intent):
            forced_urls.extend(urls_for_intent(valid_urls, intent))

    forced_docs: List[Document] = []
    if forced_urls:
        stored = _documents_for_church(vector_db, church_id)
        forced_docs = _best_chunk_per_url(stored, forced_urls, query)

    search_kwargs = {"k": SEMANTIC_K}
    if church_id:
        search_kwargs["filter"] = {"church_id": church_id}
    ranked_pairs = vector_db.similarity_search_with_relevance_scores(query, **search_kwargs)

    merged = {}
    for doc, relevance in ranked_pairs:
        merged[_signature(doc)] = (doc, float(relevance))
    for doc in forced_docs:
        signature = _signature(doc)
        if signature not in merged:
            merged[signature] = (doc, FORCED_RELEVANCE)

    if not merged:
        return []

    scored = []
    for doc, relevance in merged.values():
        source = doc.metadata.get("source", "")
        final = relevance + url_adjustment(
            source, query, valid_urls, preferred_campus_keyword, profile
        )
        scored.append((doc, final))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [doc for doc, _score in scored[:RESULT_LIMIT]]
