"""Church registry — config-as-code for multi-tenant deployments."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


class UnknownChurchError(KeyError):
    pass


@dataclass(frozen=True)
class IntentRule:
    any_terms: tuple[str, ...] = ()
    all_terms: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    include_site_root: bool = False
    prefer_specific: bool = False
    limit: int = 3


@dataclass(frozen=True)
class RetrievalProfile:
    high_value: tuple[str, ...]
    low_value: tuple[str, ...]
    intents: tuple[IntentRule, ...]


DEFAULT_RETRIEVAL = RetrievalProfile(
    high_value=(
        "service", "location", "campus", "visit", "time", "about",
        "connect", "new", "give", "giving", "donate", "team",
        "staff", "who-we-are", "leadership", "youth", "kid",
        "child", "student", "christmas",
    ),
    low_value=(
        "event", "pantry", "easter", "calendar", "blog",
        "news", "message", "sermon",
    ),
    intents=(
        IntentRule(
            any_terms=("visit", "new"),
            all_terms=("service", "times"),
            paths=("/locations/", "/campuses/", "/contact", "/visit"),
            include_site_root=True,
            prefer_specific=True,
            limit=6,
        ),
        IntentRule(
            any_terms=("give", "giving", "donate", "tithe"),
            paths=("/give", "/giving", "/donate"),
            limit=2,
        ),
        IntentRule(
            any_terms=("pastor", "team", "staff", "leader"),
            paths=("/team", "/staff", "/leadership", "/who-we-are", "/about"),
            limit=3,
        ),
        IntentRule(
            any_terms=("youth", "kid", "child", "student", "teen"),
            paths=("/youth", "/kid", "/child", "/student"),
            limit=3,
        ),
    ),
)


@dataclass(frozen=True)
class ChurchConfig:
    church_id: str
    name: str
    domain: str
    start_url: str
    max_pages: int = 400
    preferred_keyword: Optional[str] = None
    allowed_origins: Optional[List[str]] = None
    retrieval: RetrievalProfile = DEFAULT_RETRIEVAL

    @property
    def origins(self) -> List[str]:
        if self.allowed_origins:
            return list(self.allowed_origins)
        return [
            f"https://{self.domain}",
            f"https://www.{self.domain}",
        ]


def _as_terms(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list):
        return default
    return tuple(str(item).strip().lower() for item in value if str(item).strip())


def _parse_intent(raw: Dict[str, Any]) -> IntentRule:
    limit = raw.get("limit", 3)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 3
    limit = min(max(limit, 1), 8)
    return IntentRule(
        any_terms=_as_terms(raw.get("any"), ()),
        all_terms=_as_terms(raw.get("all"), ()),
        paths=_as_terms(raw.get("paths"), ()),
        include_site_root=bool(raw.get("include_site_root", False)),
        prefer_specific=bool(raw.get("prefer_specific", False)),
        limit=limit,
    )


def _parse_retrieval(raw: Any) -> RetrievalProfile:
    if not isinstance(raw, dict):
        return DEFAULT_RETRIEVAL
    if raw.get("intents") is None:
        intents = DEFAULT_RETRIEVAL.intents
    else:
        intents = tuple(
            _parse_intent(item) for item in raw.get("intents") or [] if isinstance(item, dict)
        )
    return RetrievalProfile(
        high_value=_as_terms(raw.get("high_value"), DEFAULT_RETRIEVAL.high_value)
        if "high_value" in raw
        else DEFAULT_RETRIEVAL.high_value,
        low_value=_as_terms(raw.get("low_value"), DEFAULT_RETRIEVAL.low_value)
        if "low_value" in raw
        else DEFAULT_RETRIEVAL.low_value,
        intents=intents,
    )


def _normalize_entry(church_id: str, raw: Dict[str, Any]) -> ChurchConfig:
    domain = raw.get("domain") or ""
    start_url = raw.get("start_url") or (f"https://{domain}" if domain else "")
    return ChurchConfig(
        church_id=church_id,
        name=raw.get("name") or church_id,
        domain=domain,
        start_url=start_url,
        max_pages=int(raw.get("max_pages") or config.MAX_PAGES),
        preferred_keyword=raw.get("preferred_keyword"),
        allowed_origins=raw.get("allowed_origins"),
        retrieval=_parse_retrieval(raw.get("retrieval")) if "retrieval" in raw else DEFAULT_RETRIEVAL,
    )


def load_registry(path: Optional[Path] = None) -> Dict[str, ChurchConfig]:
    registry_path = path or config.CHURCHES_FILE
    with open(registry_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Support both new {"churches": {...}} and legacy flat {id: {...}}
    if "churches" in payload and isinstance(payload["churches"], dict):
        entries = payload["churches"]
    else:
        entries = {k: v for k, v in payload.items() if isinstance(v, dict)}

    return {cid: _normalize_entry(cid, data) for cid, data in entries.items()}


def get_church(church_id: str, path: Optional[Path] = None) -> ChurchConfig:
    churches = load_registry(path)
    if church_id not in churches:
        raise UnknownChurchError(
            f"Unknown church_id '{church_id}'. Known: {', '.join(sorted(churches)) or '(none)'}"
        )
    return churches[church_id]


def list_church_ids(path: Optional[Path] = None) -> List[str]:
    return sorted(load_registry(path).keys())


def all_allowed_origins(path: Optional[Path] = None) -> List[str]:
    origins: List[str] = []
    for church in load_registry(path).values():
        origins.extend(church.origins)
    # Preserve order, drop dupes
    seen = set()
    unique = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            unique.append(o)
    return unique
