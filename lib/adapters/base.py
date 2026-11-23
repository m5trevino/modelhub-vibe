"""Shared adapter types and helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# The user wants this exact Hetzner model as the active default everywhere.
PREFERRED_DEFAULT = ("hetzner", "Qwen/Qwen3.6-35B-A3B-FP8")


@dataclass
class FileWrite:
    path: Path
    content: str
    fmt: str = "json"
    mode: int = 0o600
    delete: bool = False


@dataclass
class Plan:
    app: str
    label: str
    files: list[FileWrite] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    note: str = ""


def key_for(keys: dict, model: dict) -> str | None:
    """Resolve the API key for a model.

    Preference order:
    1. A key already proven in the existing droid settings for this exact
       baseUrl (the user's working config is ground truth).
    2. The key from the env file under the model's keyEnv.
    """
    proven = proven_keys_by_baseurl().get(model.get("baseUrl") or "")
    if proven:
        return proven
    return keys.get(model.get("keyEnv", "")) or None


_PROVEN_KEYS: dict[str, str] | None = None


def proven_keys_by_baseurl() -> dict[str, str]:
    """baseUrl -> apiKey, read from the existing ~/.factory/settings.json.

    Entries there were written by hand or by a known-good sync, so their keys
    are preferred over whatever pool ordering the env file happens to have.
    Read-only; cached after first call.
    """
    global _PROVEN_KEYS
    if _PROVEN_KEYS is not None:
        return _PROVEN_KEYS
    out: dict[str, str] = {}
    import json
    p = Path.home() / ".factory" / "settings.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for m in data.get("customModels") or []:
            b, k = m.get("baseUrl"), m.get("apiKey")
            if b and isinstance(k, str) and k and b not in out:
                # strip any LABEL: prefix defensively
                if ":" in k:
                    label, rest = k.split(":", 1)
                    import re
                    if re.match(r"^[A-Z0-9_]{1,16}$", label) and len(rest) > 20:
                        k = rest
                out[b] = k
    except Exception:
        pass
    _PROVEN_KEYS = out
    return out


def provider_slugs(models: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for m in models:
        out.setdefault(m["provider"], []).append(m)
    return out


def default_model(models: list[dict]) -> dict | None:
    """Prefer the explicit Hetzner default, then a free tool-capable model."""
    if not models:
        return None
    for m in models:
        if (m.get("provider"), m.get("apiId")) == PREFERRED_DEFAULT:
            return m

    def score(m):
        rank = {"free": 0, "tier": 1, "cost": 2, "cloud": 3}
        return (
            rank.get(m.get("freeKind"), 4),
            0 if m.get("tools") is True else 1,
            0 if (m.get("ctx") or 0) >= 64000 else 1,
            -(m.get("ctx") or 0),
            m.get("out") if m.get("out") is not None else 1e9,
            m.get("apiId", ""),
        )

    return min(models, key=score)


def input_modalities(m: dict) -> list[str]:
    mods = ["text"]
    if m.get("img") is True:
        mods.append("image")
    return mods
