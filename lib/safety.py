"""Backups, atomic writes, and format validators."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
from datetime import datetime
from pathlib import Path

import yaml

BACKUPS = Path(__file__).resolve().parent.parent / "backups"
HOME = Path.home()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path, ts: str | None = None) -> Path | None:
    """Copy `path` to `<path>.bak.<ts>` in the SAME directory, next to the
    original, so the backup is right where the user looks for it."""
    if not path.exists():
        return None
    ts = ts or stamp()
    dest = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, dest)
    os.chmod(dest, 0o600 if _has_secret(path) else 0o644)
    return dest


def _has_secret(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return bool(re.search(r"(sk-|csk-|xpl_|mg_|eyJ[A-Za-z0-9_-]{10,}|API_KEY=)", text))


def atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def strip_jsonc(text: str) -> str:
    out = []
    i, n = 0, len(text)
    in_str = esc = line = block = False
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if line:
            if c == "\n":
                line = False
                out.append(c)
            i += 1
            continue
        if block:
            if c == "*" and nxt == "/":
                block = False
                i += 2
            else:
                i += 1
            continue
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and nxt == "/":
            line = True
            i += 2
            continue
        if c == "/" and nxt == "*":
            block = True
            i += 2
            continue
        out.append(c)
        i += 1
    cleaned = "".join(out)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return cleaned


def parse_jsonc(text: str) -> dict:
    return json.loads(strip_jsonc(text))


def dumps_json(obj, indent: int = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False) + "\n"


def validate(path: Path, fmt: str) -> None:
    text = path.read_text(encoding="utf-8")
    if fmt == "json":
        json.loads(text)
    elif fmt == "jsonc":
        parse_jsonc(text)
    elif fmt == "yaml":
        yaml.safe_load(text)
    elif fmt == "toml":
        tomllib.loads(text)
    else:
        raise ValueError(f"unknown format {fmt}")


def restore(path: Path, backup_path: Path) -> None:
    shutil.copy2(backup_path, path)
    if _has_secret(path):
        os.chmod(path, 0o600)
