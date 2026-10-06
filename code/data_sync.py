"""S3 / local bundle sync for per-church knowledge bases."""
from __future__ import annotations

import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import config
from logging_config import setup_logging

logger = setup_logging()


def _s3_client():
    import boto3

    return boto3.client("s3")


def _lambda_client():
    import boto3

    return boto3.client("lambda")


def write_manifest(church_id: str, runtime_dir: Path, **fields: Any) -> Dict[str, Any]:
    manifest = {
        "church_id": church_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": config.EMBEDDING_MODEL_NAME,
        "llm_model": config.LLM_MODEL_NAME,
        **fields,
    }
    path = runtime_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_bundle(church_id: str, runtime_dir: Path, zip_path: Optional[Path] = None) -> Path:
    runtime_dir = Path(runtime_dir)
    chroma = runtime_dir / "chroma_db"
    data = runtime_dir / "scraped_data.jsonl"
    manifest = runtime_dir / "manifest.json"

    if not chroma.exists():
        raise FileNotFoundError(f"Missing chroma_db at {chroma}")
    if not data.exists():
        raise FileNotFoundError(f"Missing scraped_data.jsonl at {data}")
    if not manifest.exists():
        raise FileNotFoundError(f"Missing manifest.json at {manifest}")

    out = Path(zip_path) if zip_path else (runtime_dir / f"{church_id}.zip")
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in chroma.rglob("*"):
            if file_path.is_file():
                arcname = Path("chroma_db") / file_path.relative_to(chroma)
                zf.write(file_path, arcname.as_posix())
        zf.write(data, "scraped_data.jsonl")
        zf.write(manifest, "manifest.json")

    logger.info("bundle_built", extra={"extra_fields": {"church_id": church_id, "bytes": out.stat().st_size}})
    return out


def extract_bundle(zip_path: Path, dest_dir: Path) -> None:
    dest_dir = Path(dest_dir)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    # Normalize layout if zip rooted oddly
    nested = dest_dir / "chroma_db"
    if not nested.exists():
        # Look one level deeper
        for child in dest_dir.iterdir():
            candidate = child / "chroma_db"
            if candidate.exists():
                for item in child.iterdir():
                    target = dest_dir / item.name
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    shutil.move(str(item), str(target))
                break


def download_bundle(bucket: str, church_id: str, dest_dir: Path) -> Path:
    """
    Download `{church_id}.zip` from S3 and extract into dest_dir.

    The zip is saved outside dest_dir so extract_bundle can safely wipe dest_dir.
    """
    dest_dir = Path(dest_dir)
    # Keep the archive outside the extract target (previous bug deleted the zip mid-extract)
    zip_path = Path(config.RUNTIME_DIR) / f"{church_id}.download.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    s3 = _s3_client()
    s3.download_file(bucket, f"{church_id}.zip", str(zip_path))
    try:
        extract_bundle(zip_path, dest_dir)
    finally:
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info(
        "bundle_downloaded",
        extra={"extra_fields": {"church_id": church_id, "bucket": bucket}},
    )
    return dest_dir


def upload_bundle(bucket: str, church_id: str, zip_path: Path, manifest: Dict[str, Any]) -> None:
    s3 = _s3_client()
    s3.upload_file(str(zip_path), bucket, f"{church_id}.zip")
    s3.put_object(
        Bucket=bucket,
        Key=f"{church_id}.manifest.json",
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info(
        "bundle_uploaded",
        extra={"extra_fields": {"church_id": church_id, "bucket": bucket, "key": f"{church_id}.zip"}},
    )


def head_remote_manifest(bucket: str, church_id: str) -> Optional[Dict[str, Any]]:
    try:
        s3 = _s3_client()
        obj = s3.get_object(Bucket=bucket, Key=f"{church_id}.manifest.json")
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.warning(
            "remote_manifest_unavailable",
            extra={"extra_fields": {"church_id": church_id, "error": str(e)}},
        )
        return None


def invalidate_chat_function(function_name: str, data_version: str) -> None:
    """Bump DATA_VERSION on the chat Lambda to recycle warm containers."""
    client = _lambda_client()
    current = client.get_function_configuration(FunctionName=function_name)
    env = current.get("Environment", {}).get("Variables", {}) or {}
    env["DATA_VERSION"] = data_version
    client.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": env},
    )
    logger.info(
        "chat_invalidated",
        extra={"extra_fields": {"function": function_name, "data_version": data_version}},
    )
