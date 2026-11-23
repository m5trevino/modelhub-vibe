"""Qwen Code adapter."""
from __future__ import annotations

import json
from pathlib import Path

from ..safety import dumps_json
from .base import FileWrite, Plan, default_model

PATH = Path.home() / ".qwen" / "settings.json"


def build(models: list[dict], keys: dict) -> Plan:
    config = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}
    buckets = config.setdefault("modelProviders", {})

    entries = []
    seen = set()
    for m in models:
        k = (m["apiId"], m["baseUrl"])
        if k in seen:
            continue
        seen.add(k)
        entries.append({
            "id": m["apiId"],
            "name": m["display"],
            "baseUrl": m["baseUrl"],
            "envKey": m["keyEnv"],
        })

    replaced = len(buckets.get("openai") or [])
    buckets["openai"] = entries

    pref = default_model(models)
    model_sel = config.get("model") if isinstance(config.get("model"), dict) else {}
    if pref:
        model_sel["name"] = pref["apiId"]
        config["model"] = model_sel

    return Plan(
        app="qwen",
        label="Qwen Code",
        files=[FileWrite(PATH, dumps_json(config), "json", 0o600)],
        stats={"managed": len(entries), "replaced": replaced},
        warnings=[],
        note="per-model envKey keeps each endpoint on its own key; hot-reloads",
    )
