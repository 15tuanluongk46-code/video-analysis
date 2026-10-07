"""Cache with TTL and size limits."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

TTL_HOURS = 24
MAX_BYTES = 5 * 1024**3
MANIFEST_NAME = "manifest.json"
EVIDENCE_NAME = "evidence.json"


def cache_root() -> Path:
    override = os.environ.get("VIDEO_ANALYZER_CACHE")
    root = Path(override) if override else Path.home() / ".cache" / "opencode" / "video-analyzer"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_id_for(url: str, resolved_media_url: str | None = None) -> str:
    key = f"{url}\n{resolved_media_url or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def entry_dir(cache_id: str) -> Path:
    return cache_root() / cache_id


def manifest_path(cache_id: str) -> Path:
    return entry_dir(cache_id) / MANIFEST_NAME


def evidence_path(cache_id: str) -> Path:
    return entry_dir(cache_id) / EVIDENCE_NAME


def load_manifest(cache_id: str) -> dict | None:
    path = manifest_path(cache_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_manifest(cache_id: str, manifest: dict) -> None:
    path = manifest_path(cache_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def create_entry(
    cache_id: str, source_url: str, resolved_media_url: str | None = None
) -> dict:
    now = time.time()
    manifest = {
        "cache_id": cache_id,
        "source_url": source_url,
        "resolved_media_url": resolved_media_url,
        "created_at": now,
        "updated_at": now,
        "status": "in_progress",
        "media": None,
        "frames": [],
        "transcript_file": None,
        "vision": None,
        "analyzed_intervals": [],
        "errors": [],
    }
    entry_dir(cache_id).mkdir(parents=True, exist_ok=True)
    save_manifest(cache_id, manifest)
    return manifest


def touch(cache_id: str) -> None:
    manifest = load_manifest(cache_id)
    if manifest is None:
        return
    manifest["updated_at"] = time.time()
    save_manifest(cache_id, manifest)


def is_fresh(manifest: dict | None, ttl_hours: float = TTL_HOURS, now: float | None = None) -> bool:
    if not manifest:
        return False
    now = now if now is not None else time.time()
    stamp = manifest.get("updated_at") or manifest.get("created_at") or 0
    return (now - stamp) <= ttl_hours * 3600


def get_fresh(cache_id: str, ttl_hours: float = TTL_HOURS) -> dict | None:
    manifest = load_manifest(cache_id)
    if manifest and is_fresh(manifest, ttl_hours) and manifest.get("status") == "completed":
        return manifest
    return None


def entry_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def list_entries() -> list[dict]:
    root = cache_root()
    rows = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        manifest = load_manifest(child.name) or {}
        rows.append(
            {
                "cache_id": child.name,
                "path": str(child),
                "created_at": manifest.get("created_at", child.stat().st_mtime),
                "updated_at": manifest.get("updated_at", child.stat().st_mtime),
                "status": manifest.get("status", "unknown"),
                "size_bytes": entry_size(child),
                "fresh": is_fresh(manifest),
            }
        )
    rows.sort(key=lambda row: row["updated_at"], reverse=True)
    return rows


def total_size() -> int:
    return sum(row["size_bytes"] for row in list_entries())


def remove_entry(cache_id: str) -> None:
    shutil.rmtree(entry_dir(cache_id), ignore_errors=True)


def cleanup(max_age_hours: float = TTL_HOURS) -> dict:
    now = time.time()
    removed = []
    for row in list_entries():
        age_hours = (now - row["updated_at"]) / 3600
        if age_hours > max_age_hours:
            remove_entry(row["cache_id"])
            removed.append(row["cache_id"])
    return {"removed": removed, "removed_count": len(removed), "total_bytes": total_size()}


def enforce_limits(max_bytes: int = MAX_BYTES, ttl_hours: float = TTL_HOURS) -> dict:
    cleanup(ttl_hours)
    evicted = []
    size = total_size()
    if size <= max_bytes:
        return {"evicted": evicted, "total_bytes": size}
    for row in sorted(list_entries(), key=lambda item: item["updated_at"]):
        if size <= max_bytes:
            break
        remove_entry(row["cache_id"])
        evicted.append(row["cache_id"])
        size -= row["size_bytes"]
    return {"evicted": evicted, "total_bytes": total_size()}


def cache_info(cache_id: str | None = None) -> dict:
    if cache_id:
        manifest = load_manifest(cache_id)
        if manifest is None:
            return {"found": False, "cache_id": cache_id}
        return {
            "found": True,
            "cache_id": cache_id,
            "fresh": is_fresh(manifest),
            "status": manifest.get("status"),
            "size_bytes": entry_size(entry_dir(cache_id)),
            "path": str(entry_dir(cache_id)),
            "manifest": manifest,
        }
    entries = list_entries()
    return {
        "found": bool(entries),
        "entries": entries,
        "total_bytes": sum(row["size_bytes"] for row in entries),
        "max_bytes": MAX_BYTES,
        "ttl_hours": TTL_HOURS,
    }
