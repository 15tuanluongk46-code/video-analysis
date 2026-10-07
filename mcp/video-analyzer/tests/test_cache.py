import os
import time

import pytest

from video_analyzer import cache


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_ANALYZER_CACHE", str(tmp_path))
    yield tmp_path


def test_cache_id_stable_and_url_specific():
    a = cache.cache_id_for("https://x.com/a")
    assert a == cache.cache_id_for("https://x.com/a")
    assert a != cache.cache_id_for("https://x.com/b")
    assert a != cache.cache_id_for("https://x.com/a", "https://cdn/a.mp4")


def test_create_and_load_manifest():
    cid = cache.cache_id_for("https://x.com/a")
    manifest = cache.create_entry(cid, "https://x.com/a")
    assert manifest["status"] == "in_progress"
    loaded = cache.load_manifest(cid)
    assert loaded["source_url"] == "https://x.com/a"
    assert cache.is_fresh(loaded)


def test_ttl_expiry():
    cid = cache.cache_id_for("https://x.com/old")
    manifest = cache.create_entry(cid, "https://x.com/old")
    stale = dict(manifest, created_at=time.time() - 25 * 3600, updated_at=time.time() - 25 * 3600)
    assert not cache.is_fresh(stale)
    assert cache.is_fresh(stale, ttl_hours=48)


def test_get_fresh_requires_completed():
    cid = cache.cache_id_for("https://x.com/p")
    cache.create_entry(cid, "https://x.com/p")
    assert cache.get_fresh(cid) is None
    manifest = cache.load_manifest(cid)
    manifest["status"] = "completed"
    cache.save_manifest(cid, manifest)
    assert cache.get_fresh(cid) is not None


def test_cleanup_removes_expired_only():
    old = cache.cache_id_for("https://x.com/old")
    new = cache.cache_id_for("https://x.com/new")
    cache.create_entry(old, "https://x.com/old")
    cache.create_entry(new, "https://x.com/new")
    manifest = cache.load_manifest(old)
    manifest["updated_at"] = time.time() - 30 * 3600
    cache.save_manifest(old, manifest)
    result = cache.cleanup(max_age_hours=24)
    assert result["removed"] == [old]
    assert cache.load_manifest(new) is not None
    assert cache.load_manifest(old) is None


def test_enforce_limits_evicts_oldest_first():
    ids = []
    for name in ("a", "b", "c"):
        cid = cache.cache_id_for(f"https://x.com/{name}")
        cache.create_entry(cid, f"https://x.com/{name}")
        (cache.entry_dir(cid) / "blob.bin").write_bytes(b"x" * 1000)
        ids.append(cid)
    manifest = cache.load_manifest(ids[0])
    manifest["updated_at"] = time.time() - 100
    cache.save_manifest(ids[0], manifest)
    result = cache.enforce_limits(max_bytes=2000)
    assert ids[0] in result["evicted"]
    assert cache.load_manifest(ids[2]) is not None


def test_cache_info_lists_entries():
    cid = cache.cache_id_for("https://x.com/z")
    cache.create_entry(cid, "https://x.com/z")
    info = cache.cache_info()
    assert info["found"]
    assert info["entries"][0]["cache_id"] == cid
    single = cache.cache_info(cid)
    assert single["found"]
    assert cache.cache_info("doesnotexist")["found"] is False
