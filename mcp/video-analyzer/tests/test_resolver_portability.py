"""Test helper command selection without any network or subprocess calls."""
import importlib.util
import os
from pathlib import Path
import sys


def test_resolver_does_not_use_authors_venv(monkeypatch):
    script = Path(__file__).resolve().parents[3] / "skills/video-analysis/scripts/resolve_media.py"
    spec = importlib.util.spec_from_file_location("resolve_media_portability", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    # Even when the author's path happens to exist, it must not be borrowed.
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    attempted = []

    def resolve(cmd, url):
        attempted.append(cmd)
        return None

    monkeypatch.setattr(module, "_ytdlp_url", resolve)
    assert module.resolve_ytdlp("https://example.com/watch") is None
    assert attempted == [[sys.executable, "-m", "yt_dlp"]]
