"""Kimchi adapter (models.json + settings.json + auth.json)."""
from __future__ import annotations

import json
from pathlib import Path

from ..catalog import PROVIDERS
from ..safety import dumps_json
from .base import FileWrite, Plan, default_model, input_modalities, provider_slugs, proven_keys_by_baseurl

MODELS = Path.home() / ".config" / "kimchi" / "harness" / "models.json"
SETTINGS = Path.home() / ".config" / "kimchi" / "harness" / "settings.json"
AUTH = Path.home() / ".config" / "kimchi" / "harness" / "auth.json"
KNOWN_BASES = {p["base"] for p in PROVIDERS.values()}


def _kimchi_slug(slug: str) -> str:
    if slug == "ollama":
        return "ollama-cloud"
    if slug == "hetzner":
        return "hetzner-inference"
    return slug


# Every provider slug that maps to a Pi auth.json credential entry.
_MANAGED_AUTH_SLUGS = {_kimchi_slug(s) for s in PROVIDERS}


def _dumps_models(doc: dict) -> str:
    """Match Kimchi's own rewrite format so `modelhub plan` stays quiet.

    Kimchi rewrites models.json with tab indentation. It also keeps its own
    bundled providers first, sorted alphabetically, followed by any extra
    providers (e.g. kimchi-dev). The caller is responsible for that order.
    """
    return json.dumps(doc, indent="\t", ensure_ascii=False)


def _load_auth() -> dict:
    if not AUTH.exists():
        return {}
    try:
        data = json.loads(AUTH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def build_documents(models: list[dict], keys: dict,
                    doc: dict | None = None,
                    settings: dict | None = None,
                    auth: dict | None = None):
    doc = doc if doc is not None else {"providers": {}}
    settings = settings if settings is not None else {}
    auth = auth if auth is not None else {}
    providers = doc.setdefault("providers", {})
    groups = provider_slugs(models)
    warnings: list[str] = []

    for slug in list(providers):
        if slug in PROVIDERS or (providers[slug] or {}).get("baseUrl") in KNOWN_BASES:
            del providers[slug]

    # Sync credentials for every provider modelhub manages. Unknown entries
    # (e.g. manually-logged-in providers) are left untouched.
    managed_keys = 0
    for slug in list(auth):
        if slug in _MANAGED_AUTH_SLUGS and slug not in {_kimchi_slug(s) for s in groups}:
            del auth[slug]

    for slug, items in groups.items():
        meta = PROVIDERS[slug]
        out_slug = _kimchi_slug(slug)
        entries = []
        for m in items:
            entry = {
                "id": m["apiId"],
                "name": m["display"],
                "input": input_modalities(m),
                "provider": "generic-chat-completion-api",
                "cost": {
                    "input": m.get("in") or 0,
                    "output": m.get("out") or 0,
                    "cacheRead": 0,
                    "cacheWrite": 0,
                },
            }
            if m.get("maxout"):
                entry["maxTokens"] = int(m["maxout"])
            if m.get("ctx"):
                entry["contextWindow"] = int(m["ctx"])
            entries.append(entry)

        providers[out_slug] = {
            "baseUrl": meta["base"],
            "apiKey": "$" + meta["key"],
            "api": "openai-completions",
            "models": entries,
        }

        key = proven_keys_by_baseurl().get(meta["base"]) or keys.get(meta["key"])
        if key:
            auth[out_slug] = {"type": "api_key", "key": key}
            managed_keys += 1
        else:
            auth.pop(out_slug, None)
            warnings.append(f"missing key for {out_slug} ({meta['key']})")

    # Order providers the same way Kimchi does: managed providers sorted
    # alphabetically, then any hand-written / extension providers in their
    # original order.
    managed_slugs = sorted({s for s in providers if s in _MANAGED_AUTH_SLUGS})
    other_slugs = [s for s in providers if s not in _MANAGED_AUTH_SLUGS]
    doc["providers"] = {k: providers[k] for k in managed_slugs + other_slugs}

    pref = default_model(models)
    if pref:
        dp = _kimchi_slug(pref["provider"])
        old_p = settings.get("defaultProvider")
        old_m = settings.get("defaultModel")
        settings["defaultProvider"] = dp
        settings["defaultModel"] = pref["apiId"]
        if (old_p, old_m) != (dp, pref["apiId"]):
            warnings.append(f"default set to {dp}/{pref['apiId']}")

    return doc, settings, auth, warnings, managed_keys


def build(models: list[dict], keys: dict) -> Plan:
    doc = json.loads(MODELS.read_text(encoding="utf-8")) if MODELS.exists() else {"providers": {}}
    settings = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    auth = _load_auth()
    doc, settings, auth, warnings, managed_keys = build_documents(models, keys, doc, settings, auth)
    groups = provider_slugs(models)
    return Plan(
        app="kimchi",
        label="Kimchi",
        files=[
            FileWrite(MODELS, _dumps_models(doc), "json", 0o600),
            FileWrite(SETTINGS, dumps_json(settings), "json", 0o600),
            FileWrite(AUTH, dumps_json(auth), "json", 0o600),
        ],
        stats={"managed": sum(len(v) for v in groups.values()), "providers": len(groups), "keys": managed_keys},
        warnings=warnings,
        note="provider keys resolved from auth.json; models.json keeps $ENV references",
    )
