"""Hermes adapter (YAML, comment-preserving)."""
from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

from ..catalog import PROVIDERS
from .base import FileWrite, Plan, default_model, provider_slugs

PATH = Path.home() / ".hermes" / "config.yaml"


def build(models: list[dict], keys: dict) -> Plan:
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(PATH, encoding="utf-8") as f:
        doc = yaml.load(f)

    providers = doc.setdefault("providers", {})
    groups = provider_slugs(models)
    warnings: list[str] = []
    replaced = 0

    for slug, items in groups.items():
        meta = PROVIDERS[slug]
        block = providers.get(slug)
        if block is None:
            block = {}
            providers[slug] = block
        block["api"] = meta["base"]
        block["key_env"] = meta["key"]

        model_map = {}
        for m in items:
            entry = {}
            if m.get("ctx"):
                entry["context_length"] = int(m["ctx"])
            model_map[m["apiId"]] = entry
        block["models"] = model_map
        pref = default_model(items)
        block["default_model"] = pref["apiId"] if pref else next(iter(model_map))
        replaced += 1

    active = doc.get("model")
    if isinstance(active, dict):
        slug = active.get("provider")
        if slug in groups:
            model_map = providers[slug]["models"]
            if active.get("default") not in model_map:
                pref = default_model(groups[slug])
                active["default"] = pref["apiId"] if pref else next(iter(model_map))
                warnings.append(f"active model re-pointed to {active['default']}")
            active["base_url"] = PROVIDERS[slug]["base"]

    pref = default_model(models)
    if pref:
        doc["model"] = {
            "default": pref["apiId"],
            "provider": pref["provider"],
            "base_url": PROVIDERS[pref["provider"]]["base"],
            "api_mode": "chat_completions",
            "parser": "hermes",
            "stream": True,
        }
        warnings.append(f"default set to {pref['provider']}/{pref['apiId']}")

    buf = io.StringIO()
    yaml.dump(doc, buf)

    return Plan(
        app="hermes",
        label="Hermes",
        files=[FileWrite(PATH, buf.getvalue(), "yaml", 0o600)],
        stats={"managed": sum(len(v) for v in groups.values()), "providers": replaced},
        warnings=warnings,
        note="comments preserved via ruamel.yaml",
    )
