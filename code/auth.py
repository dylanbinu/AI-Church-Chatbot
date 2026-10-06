"""Optional API-key auth for the chat API."""
from __future__ import annotations

import secrets
from typing import List, Optional

from fastapi import Header, HTTPException, status

import config


def is_auth_enabled() -> bool:
    return bool(config.API_KEYS)


def key_matches(provided: Optional[str], allowed: List[str]) -> bool:
    if not provided:
        return False
    return any(secrets.compare_digest(provided, candidate) for candidate in allowed)


async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if not is_auth_enabled():
        return
    if not key_matches(x_api_key, config.API_KEYS):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
