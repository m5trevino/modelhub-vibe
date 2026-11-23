"""Pi (pi-dev) adapter."""
from __future__ import annotations

import json
from pathlib import Path

from ..catalog import PROVIDERS
from ..safety import dumps_json
from .base import FileWrite, Plan, input_modalities, provider_slugs

PATH = Path.home() / ".pi" / "agent" / "models.json"
KNOWN_BASES = {p["base"] for p in PROVIDERS.values()}


def build(models: list[dict], keys: dict) -> Plan:
    config = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}
    providers = config.setdefault("providers", {})
    groups = provider_slugs(models)

    for slug in list(providers):
        if slug in PROVIDERS or (providers[slug] or {}).get("baseUrl") in KNOWN_BASES:
            del providers[slug]

    for slug, items in groups.items():
        providers[slug] = {
            "baseUrl": PROVIDERS[slug]["base"],
            "models": [
                {"id": m["apiId"], "input": input_modalities(m)}
                for m in items
            ],
        }

    return Plan(
        app="pi",
        label="Pi (pi-dev)",
        files=[FileWrite(PATH, dumps_json(config), "json", 0o600)],
        stats={"managed": sum(len(v) for v in groups.values()), "providers": len(groups)},
        warnings=["pi-dev wrapper currently cd's into a missing directory; config is valid but the launcher needs fixing"]
        if not Path("/home/flintx/projects/pi-src/pi").exists() else [],
        note="providers grouped by endpoint, not by protocol",
    )
