"""OpenCode and Kilo adapter (JSONC, OpenAI-compatible providers)."""
from __future__ import annotations

import json
from pathlib import Path

from ..catalog import PROVIDERS
from ..safety import dumps_json, parse_jsonc
from .base import FileWrite, Plan, default_model, provider_slugs

OPENCODE = Path.home() / ".config" / "opencode" / "opencode.jsonc"
KILO = Path.home() / ".config" / "kilo" / "kilo.jsonc"
KNOWN_BASES = {p["base"] for p in PROVIDERS.values()}


def build(models: list[dict], keys: dict, path: Path = OPENCODE, app: str = "opencode",
          label: str = "OpenCode") -> Plan:
    text = path.read_text(encoding="utf-8") if path.exists() else '{"$schema":"https://opencode.ai/config.json"}'
    config = parse_jsonc(text)
    providers = config.setdefault("provider", {})
    groups = provider_slugs(models)
    warnings: list[str] = []
    replaced = 0

    # Replace every provider whose endpoint we own, so stale paid entries
    # do not linger next to the fresh free set.
    for slug in list(providers):
        opts = (providers[slug] or {}).get("options") or {}
        if slug in PROVIDERS or opts.get("baseURL") in KNOWN_BASES:
            del providers[slug]

    for slug, items in groups.items():
        meta = PROVIDERS[slug]
        model_map = {}
        for m in items:
            entry = {"name": m["display"]}
            if m.get("ctx") and m.get("maxout"):
                entry["limit"] = {
                    "context": int(m["ctx"]),
                    "output": int(m["maxout"]),
                }
            model_map[m["apiId"]] = entry

        providers[slug] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": meta["name"],
            "options": {
                "baseURL": meta["base"],
                "apiKey": "${" + meta["key"] + "}",
            },
            "models": model_map,
        }
        replaced += 1

    pref = default_model(models)
    if pref:
        config["model"] = f"{pref['provider']}/{pref['apiId']}"

    # Keep $schema first for editor completion.
    ordered = {}
    if "$schema" in config:
        ordered["$schema"] = config.pop("$schema")
    ordered.update(config)

    return Plan(
        app=app,
        label=label,
        files=[FileWrite(path, dumps_json(ordered), "jsonc", 0o600)],
        stats={"managed": sum(len(v) for v in groups.values()), "providers": replaced},
        warnings=warnings,
        note="JSONC comments are not preserved; a timestamped backup is taken first",
    )
