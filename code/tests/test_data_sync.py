"""Unit tests for bundle packaging."""
import json
from pathlib import Path

from data_sync import build_bundle, write_manifest


def test_build_bundle_includes_required_entries(tmp_path: Path):
    chroma = tmp_path / "chroma_db"
    chroma.mkdir()
    (chroma / "chroma.sqlite3").write_bytes(b"x" * 1200)
    (tmp_path / "scraped_data.jsonl").write_text(
        json.dumps({"source": "https://example.com", "content": "hello world from church site"}) + "\n",
        encoding="utf-8",
    )
    write_manifest("demo", tmp_path, pages=1, chunks=1)

    zip_path = build_bundle("demo", tmp_path)
    assert zip_path.exists()

    import zipfile

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    assert "scraped_data.jsonl" in names
    assert "manifest.json" in names
    assert any(n.startswith("chroma_db/") for n in names)


def test_download_bundle_keeps_zip_outside_dest(tmp_path, monkeypatch):
    """Regression: zip must not live inside dest_dir (extract deletes dest_dir)."""
    import zipfile
    import shutil

    import data_sync

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(data_sync.config, "RUNTIME_DIR", runtime)

    src_dir = tmp_path / "src"
    chroma = src_dir / "chroma_db"
    chroma.mkdir(parents=True)
    (chroma / "chroma.sqlite3").write_bytes(b"x" * 200)
    bundle = tmp_path / "heritage.zip"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.write(chroma / "chroma.sqlite3", "chroma_db/chroma.sqlite3")

    class FakeS3:
        def download_file(self, bucket, key, filename):
            shutil.copy2(bundle, filename)

    monkeypatch.setattr(data_sync, "_s3_client", lambda: FakeS3())

    dest = runtime / "heritage"
    data_sync.download_bundle("bucket", "heritage", dest)
    assert (dest / "chroma_db" / "chroma.sqlite3").exists()
    assert not (dest / "heritage.zip").exists()
