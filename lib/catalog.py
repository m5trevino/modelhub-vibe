"""Catalog loading, free-model policy, and display naming."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

CATALOG = Path("/home/flintx/model-catalog-site/data/catalog.json")
ENV_FILE = Path.home() / ".config" / "modelhub" / "env"

# Provider routing metadata for every gateway the engine catalog serves.
# base/key come from the engine's own provider registry (snapshot of
# https://catalog.save-aichats.com/v1/models `providers` block); key is the
# single-key env var used by ~/.config/modelhub/env.
PROVIDERS = {
    "anyapi":         dict(name="AnyAPI",         base="https://api.anyapi.ai/v1",                              key="ANYAPI_API_KEY"),
    "bazaarlink":     dict(name="Bazaarlink",     base="https://api.bazaarlink.ai/v1",                         key="BAZAARLINK_API_KEY"),
    "dreamprompting": dict(name="DreamPrompting", base="https://dreamprompting.com/api/v1",                    key="DREAMPROMPTING_API_KEY"),
    "google":         dict(name="Google",         base="https://generativelanguage.googleapis.com/v1beta/openai", key="GEMINI_API_KEY"),
    "groq":           dict(name="Groq",           base="https://api.groq.com/openai/v1",                       key="GROQ_API_KEY"),
    "hetzner":        dict(name="Hetzner",        base="https://inference.hetzner.com/v1",                     key="HETZNER_API_KEY"),
    "llm7":           dict(name="LLM7",           base="https://api.llm7.io/v1",                               key="LLM7_API_KEY"),
    "logfare":        dict(name="Logfare",        base="https://logfare.ai/v1",                                key="LOGFARE_API_KEY"),
    "merge":          dict(name="Merge",          base="https://api-gateway.merge.dev/v1",                    key="MERGE_API_KEY"),
    "mistral":        dict(name="Mistral",        base="https://api.mistral.ai/v1",                           key="MISTRAL_API_KEY"),
    "navyai":         dict(name="NavyAI",         base="https://api.navy/v1",                                 key="NAVYAI_API_KEY"),
    "novita":         dict(name="Novita",         base="https://api.novita.ai/openai/v1",                     key="NOVITA_API_KEY"),
    "nvidia-nim":     dict(name="NVIDIA NIM",     base="https://integrate.api.nvidia.com/v1",                 key="NVIDIA_NIM_API_KEY"),
    "ollama":         dict(name="Ollama",         base="https://ollama.com/v1",                               key="OLLAMA_API_KEY"),
    "openrouter":     dict(name="OpenRouter",     base="https://openrouter.ai/api/v1",                        key="OPENROUTER_API_KEY"),
    "pollinations":   dict(name="Pollinations",   base="https://gen.pollinations.ai/v1",                       key="POLLINATIONS_API_KEY"),
    "radium":         dict(name="Radium",         base="https://api.radium.cloud/v1",                         key="RADIUM_API_KEY"),
    "requesty":       dict(name="Requesty",       base="https://router.requesty.ai/v1",                       key="REQUESTY_API_KEY"),
    "routeway":       dict(name="Routeway",       base="https://api.routeway.ai/v1",                           key="ROUTEWAY_API_KEY"),
    "unorouter":      dict(name="Unorouter",      base="https://api.unorouter.ai/v1",                         key="UNOROUTER_API_KEY"),
    "xkiro":          dict(name="xKiro",          base="https://api.xkiro.com/v1",                            key="XKIRO_API_KEY"),
    "zhipu":          dict(name="Zhipu",          base="https://api.z.ai/api/paas/v4",                      key="ZHIPU_API_KEY"),
    # Kept for refresh/doctor compatibility with older catalogs.
    "septorlabs":     dict(name="Septor Labs",    base="https://api.septorlabs.com/v1",                       key="SEPTORLABS_API_KEY"),
    "airforce":       dict(name="API.Airforce",   base="https://api.airforce/v1",                             key="AIRFORCE_API_KEY"),
    "deepinfra":      dict(name="DeepInfra",      base="https://api.deepinfra.com/v1/openai",                 key="DEEPINFRA_API_KEY"),
    "clod":           dict(name="CLod",           base="https://api.clod.io/v1",                             key="CLOD_API_KEY"),
    "cerebras":       dict(name="Cerebras",       base="https://api.cerebras.ai/v1",                         key="CEREBRAS_API_KEY"),
    "experiential":   dict(name="Experiential",   base="https://api.experientiallabs.ai/v1",               key="EXPERIENTIALLABS_API_KEY"),
    "sailresearch":   dict(name="Sail Research",  base="https://api.sailresearch.com/v1",                     key="SAILRESEARCH_API_KEY"),
    "router9":        dict(name="Router9",        base="https://api.router9.com/v1",                         key="ROUTER9_API_KEY"),
}

# One symbol per gateway, cycled. The symbol lets the user search a single
# character in any app's model picker to see only that provider.
PROVIDER_SYMBOLS = ["✠", "━", "═", "⍋", "】", "ᕗ", "ᗜ", "┻", "■"]

_GATEWAY_SYMBOLS: dict[str, str] = {}


def gateway_symbol(gateway: str) -> str:
    """Stable symbol for a gateway, assigned in sorted order."""
    if not _GATEWAY_SYMBOLS:
        for i, gw in enumerate(sorted(PROVIDERS)):
            _GATEWAY_SYMBOLS[gw] = PROVIDER_SYMBOLS[i % len(PROVIDER_SYMBOLS)]
    return _GATEWAY_SYMBOLS.setdefault(
        gateway, PROVIDER_SYMBOLS[hash(gateway) % len(PROVIDER_SYMBOLS)]
    )


def clean_model_name(api_id: str) -> str:
    """Strip the vendor/org prefix and any free-style suffix."""
    name = api_id.split("/")[-1] if "/" in api_id else api_id
    if ":" in name:
        name = name.split(":")[0]
    for suffix in (":free", "free"):
        if name.lower().endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
            break
    return name


def price_tag(free_kind: str | None, inp: float, out: float) -> str:
    """⟦FREE⟧ or ⟦¢.10⤣¢.19⤤⟧ (USD per 1M tokens)."""
    if free_kind in ("free", "tier") and not inp and not out:
        return "⟦FREE⟧"

    def fmt(v: float) -> str:
        s = f"{v:.2f}"
        return s[1:] if s.startswith("0.") else s

    return f"⟦¢{fmt(inp)}⤣¢{fmt(out)}⤤⟧"


def display_name(gateway: str, api_id: str, free_kind: str | None,
                 inp: float, out: float) -> str:
    """⦗GATEWAY⦘SYMBOL clean-name ⟦tag⟧ — the binding display format."""
    return (f"⦗{gateway.upper()}⦘{gateway_symbol(gateway)} "
            f"{clean_model_name(api_id)} {price_tag(free_kind, inp, out)}")


PROFILES = {
    "strict": "free models, plus the under-$0.50 band and DeepSeek/coding at any price",
    "tier": "models on a free access tier, including priced ones",
    "cloud": "Ollama Cloud subscription models only",
    "under40": "free, free-tier, cloud, and paid models at or below $0.40 in/out",
    "all-free": "free, free-tier, Ollama Cloud, anything under $0.50, plus DeepSeek and coding models at any price",
}

NON_TEXT_KINDS = {
    "text-to-image", "text-to-video", "text-to-speech", "automatic-speech-recognition",
    "embeddings", "reranker", "image", "tts", "stt", "audio", "decision",
}

# Selection policy.
# - Paid models under PRICE_LIMIT on both input and output are listed.
# - DeepSeek and coding models are listed at any price.
# - A row with no usable price is dropped, because the price cannot be shown.
#   Ollama Cloud is exempt: it is a subscription, so no per-token price exists.
# Prices are USD per 1M tokens, which is what the catalog stores.
PRICE_LIMIT = 0.50

DEEPSEEK_NEEDLES = ("deepseek",)

CODING_NEEDLES = (
    "coder", "codestral", "devstral", "codex", "starcoder",
    "codellama", "codegemma", "codeqwen",
)

# Providers do not always tag a model's kind, so names are checked too.
# These cannot run a chat slice, so they never reach a picker.
NON_CHAT_NEEDLES = (
    "rerank", "embed", "whisper", "transcribe", "tts", "stt", "ocr",
    "bge-", "clip", "diffusion", "flux", "moderation", "guard", "audio", "speech",
)

# Hetzner Inference exposes these two models with no per-token pricing.
# Kept static because /v1/models does not return pricing or capabilities.
HETZNER_MODELS = [
    {"id": "Qwen/Qwen3.6-35B-A3B-FP8", "name": "Qwen3.6 35B A3B FP8", "ctx": 262144, "maxout": 32768},
    {"id": "Qwen/Qwen3.8-27B", "name": "Qwen3.8 27B", "ctx": 262144, "maxout": 32768},
]


def load_catalog(path: Path = CATALOG) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_keys(path: Path = ENV_FILE) -> dict:
    keys = {}
    if not path.exists():
        return keys
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def _text_kind(row: dict) -> bool:
    if row["p"] == "ollama":
        # Cloud tags include a vision/decision model that cannot chat.
        return "completion" in (row.get("kind") or "")
    if row["p"] == "merge":
        # The catalog marks text-capable vendor offers explicitly; the rest are
        # image, video, speech, or transcription models.
        return row.get("text") is not False
    kind = (row.get("kind") or "").lower()
    if not kind:
        return True
    return kind not in NON_TEXT_KINDS


def _free_kind(row: dict) -> str | None:
    if row.get("cloud") is True:
        return "cloud"
    if row.get("free") is True:
        return "free"
    if (row.get("tier") or "").lower() == "free":
        if (row.get("in") or 0) == 0 and (row.get("out") or 0) == 0:
            return "tier"
        return "cost"
    return None


def _money(v: float | None) -> str:
    if v is None:
        return "?"
    if v == 0:
        return "0"
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s


def _clean(name: str, api_id: str) -> str:
    name = re.sub(r"\s+", " ", str(name or api_id)).strip()
    name = name.replace("|", "/")
    if len(name) > 44:
        name = name[:43].rstrip() + "…"
    return name


def _tag(free_kind: str, inp: float | None, out: float | None) -> str:
    if free_kind == "cloud":
        return "[CLOUD]"
    if free_kind == "free":
        return "[FREE]"
    if free_kind == "tier" and not inp and not out:
        return "[FREE TIER]"
    # Everything else is labelled COST with the actual price attached.
    return f"[COST {_money(inp)}/{_money(out)}]"


def _haystack(row: dict) -> str:
    return f"{row.get('id') or ''} {row.get('name') or ''}".lower()


def _always_include(row: dict) -> bool:
    """DeepSeek and coding models are listed at whatever they cost."""
    hay = _haystack(row)
    if any(n in hay for n in DEEPSEEK_NEEDLES):
        return True
    return any(n in hay for n in CODING_NEEDLES)


def _non_chat(row: dict) -> bool:
    """Embedding, reranking, speech, and OCR models cannot run a slice."""
    hay = _haystack(row)
    return any(n in hay for n in NON_CHAT_NEEDLES)


def build_models(profile: str = "all-free", catalog: dict | None = None) -> list[dict]:
    """Return deduped, named model routes ready for app adapters."""
    catalog = catalog or load_catalog()
    rows = catalog.get("models") or []

    picked: dict[tuple, dict] = {}
    for row in rows:
        if row.get("status") == "deprecated":
            continue
        if not _text_kind(row):
            continue
        if _non_chat(row):
            continue
        fk = _free_kind(row)
        inp, out = row.get("in"), row.get("out")
        priced = isinstance(inp, (int, float)) and isinstance(out, (int, float))
        cheap = priced and inp < PRICE_LIMIT and out < PRICE_LIMIT
        wanted = _always_include(row)

        # A row classified as costing money must carry a full price pair,
        # otherwise the cost cannot be rendered and it does not get listed.
        if fk == "cost" and not priced:
            continue

        if profile == "under40":
            # Engine profile keeps its original $0.40 band, no force-includes.
            if fk is None:
                if not priced or inp > 0.4 or out > 0.4:
                    continue
                fk = "cheap"
        elif fk == "cloud":
            pass                      # subscription bucket, no per-token price
        elif wanted:
            if not priced:
                continue              # forced in, but there is no price to render
            if fk is None:
                fk = "cheap" if cheap else "cost"
        elif fk is None:
            if not cheap:
                continue
            fk = "cheap"
        elif profile == "strict" and fk != "free":
            continue
        elif profile == "tier" and fk in ("free", "cloud"):
            continue
        elif profile == "cloud":
            continue
        elif profile == "all-free" and fk not in ("free", "tier", "cost"):
            continue

        provider = row["p"]
        meta = PROVIDERS.get(provider)
        if not meta:
            continue

        key = (provider, row["id"])
        current = picked.get(key)
        # One API id per provider. For Merge, keep the cheapest vendor offer.
        if current is not None:
            if provider == "merge":
                if (row.get("out") or 0) >= (current.get("out") or 0):
                    continue
            else:
                continue

        picked[key] = {
            "provider": provider,
            "providerName": meta["name"],
            "baseUrl": meta["base"],
            "keyEnv": meta["key"],
            "apiId": row["id"],
            "name": _clean(row.get("name"), row["id"]),
            "ctx": row.get("ctx"),
            "maxout": row.get("maxout"),
            "in": row.get("in"),
            "out": row.get("out"),
            "img": row.get("img"),
            "tools": row.get("tools"),
            "vendor": row.get("vendor"),
            "tier": row.get("tier"),
            "freeKind": fk,
                }

    # Hetzner is a standing entitlement: always present, in every profile.
    hetzner = PROVIDERS["hetzner"]
    for hm in HETZNER_MODELS:
        key = ("hetzner", hm["id"])
        if key in picked:
            continue
        picked[key] = {
            "provider": "hetzner",
            "providerName": "Hetzner",
            "baseUrl": hetzner["base"],
            "keyEnv": hetzner["key"],
            "apiId": hm["id"],
            "name": hm["name"],
            "ctx": hm["ctx"],
            "maxout": hm["maxout"],
            "in": 0.0,
            "out": 0.0,
            "img": True,
            "tools": True,
            "vendor": None,
            "tier": "free",
            "freeKind": "free",
        }

    models = sorted(picked.values(), key=lambda m: (m["provider"], m["apiId"].lower()))

    # Display names must be unique inside a picker.
    counts: dict[str, int] = {}
    for m in models:
        suffix = f" / {m['vendor']}" if m.get("vendor") else ""
        display = f"{_tag(m['freeKind'], m['in'], m['out'])} {m['name']} — {m['provider']}{suffix}"
        n = counts.get(display, 0) + 1
        counts[display] = n
        if n > 1:
            display = f"{display} ({n})"
        m["display"] = display

    return models


def route_key(m: dict) -> str:
    """Stable internal identity, independent of the display string."""
    vendor = f":{m['vendor']}" if m.get("vendor") else ""
    return f"hub:{m['provider']}:{m['apiId']}{vendor}"


def summarize(models: list[dict]) -> dict:
    by_provider: dict[str, int] = {}
    for m in models:
        by_provider[m["provider"]] = by_provider.get(m["provider"], 0) + 1
    return {
        "total": len(models),
        "providers": by_provider,
        "tools": sum(1 for m in models if m.get("tools") is True),
        "image": sum(1 for m in models if m.get("img") is True),
        "free": sum(1 for m in models if m["freeKind"] == "free"),
        "tier": sum(1 for m in models if m["freeKind"] in ("tier", "cost")),
        "cloud": sum(1 for m in models if m["freeKind"] == "cloud"),
        "cheap": sum(1 for m in models if m["freeKind"] == "cheap"),
    }
