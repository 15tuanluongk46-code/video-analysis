#!/usr/bin/env python3
"""Resolve a social video URL to a direct media URL.

Usage:
    python3 resolve_media.py <url>

X/Twitter: vxtwitter -> fxtwitter public APIs.
Other hosts (TikTok/Instagram/Facebook/YouTube/...): yt-dlp
(system CLI -> current python module).

Prints the direct media URL on stdout. Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import urllib.request

TWEET_RE = re.compile(
    r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status(?:es)?/(\d+)"
)


def resolve_twitter(url: str, timeout: float = 8.0) -> str | None:
    match = TWEET_RE.match(url)
    if not match:
        return None
    handle, tweet_id = match.group(1), match.group(2)
    endpoints = (
        (f"https://api.vxtwitter.com/{handle}/status/{tweet_id}", "curl/8.5.0"),
        (f"https://api.fxtwitter.com/{handle}/status/{tweet_id}", "Mozilla/5.0"),
    )
    for endpoint, user_agent in endpoints:
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            continue
        media_urls = data.get("mediaURLs") or []
        if media_urls:
            return str(media_urls[0])
        media = data.get("media")
        if not isinstance(media, dict):
            media = (data.get("tweet") or {}).get("media") or {}
        videos = media.get("videos") or []
        if videos and videos[0].get("url"):
            return str(videos[0]["url"])
    return None


def _ytdlp_url(cmd: list[str], url: str, timeout: float = 90.0) -> str | None:
    try:
        proc = subprocess.run(
            cmd + ["-g", "--no-playlist", "--no-warnings", url],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        candidate = line.strip()
        if candidate.startswith("http"):
            return candidate
    return None


def resolve_ytdlp(url: str) -> str | None:
    candidates: list[list[str]] = []
    if shutil.which("yt-dlp"):
        candidates.append(["yt-dlp"])
    candidates.append([sys.executable, "-m", "yt_dlp"])
    for cmd in candidates:
        resolved = _ytdlp_url(cmd, url)
        if resolved:
            return resolved
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve_media.py <url>", file=sys.stderr)
        return 1
    url = sys.argv[1].strip()
    resolved = resolve_twitter(url) or resolve_ytdlp(url)
    if not resolved:
        print(f"could not resolve media url: {url}", file=sys.stderr)
        return 1
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
