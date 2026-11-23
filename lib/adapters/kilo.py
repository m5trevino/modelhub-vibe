"""Kilo adapter. Kilo is an OpenCode fork and reads the same config shape."""
from __future__ import annotations

from pathlib import Path

from . import opencode

PATH = Path.home() / ".config" / "kilo" / "kilo.jsonc"


def build(models: list[dict], keys: dict):
    return opencode.build(models, keys, path=PATH, app="kilo", label="Kilo")
