#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""modelhub-vibe: sync the live engine model catalog to every CLI coding app.

Local machine: applies to all registered modelhub apps (droid, opencode,
kimchi, qwen, pi, kilo, goose, hermes).

Hetzner engine (ssh "engine"): pushes this script + the modelhub package to
/root, regenerates /root/.config/modelhub/env from the engine's own
ai-engine/.env key pools, and applies to the apps installed there.

Usage:
  modelhub-vibe                 fetch + apply locally + push to engine
  modelhub-vibe --dry-run       plan only, write nothing
  modelhub-vibe --no-engine     local only
  modelhub-vibe --apps droid,opencode
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

CATALOG_URLS = [
    "https://catalog.save-aichats.com/v1/models",
    "https://engine.save-aichats.com/v1/models",
]
SNAPSHOT = Path(__file__).resolve().parent / "snapshot.json"
REMOTE_MODELS = "/root/.local/share/modelhub-vibe/models_live.json"
ENGINE_ENV = "/root/.config/modelhub/env"
ENGINE_DOTENV = "/root/hetzner/ai-engine/.env"
SSH_HOST = "engine"

# The real package wins: prefer the directory this script lives in (the
# installer unpacks modelhub.py + lib/ next to it), then the known homes.
_here = str(Path(__file__).resolve().parent)
sys.path = [p for p in sys.path if p not in ("", _here)]
for _p in (_here, "/home/flintx/modelhub", "/root/modelhub"):
    if os.path.isfile(os.path.join(_p, "modelhub.py")):
        sys.path.insert(0, _p)
        break

from modelhub import cmd_apply  # noqa: E402
from lib.adapters import REGISTRY  # noqa: E402
from lib.catalog import (  # noqa: E402
    PROVIDERS, NON_CHAT_NEEDLES, gateway_symbol, clean_model_name, price_tag,
)


def display_name_for(gateway: str, name: str, free_kind, inp, outp) -> str:
    """⦗GATEWAY⦘SYM░name░SYM⟦tag⟧ — the binding display format."""
    sym = gateway_symbol(gateway)
    return (f"⦗{gateway.upper()}⦘{sym}░{name}░{sym}"
            f"{price_tag(free_kind, inp, outp)}")

NON_CHAT_KINDS = {
    "embedding", "embeddings", "reranker", "decisions", "image", "audio",
    "tts", "stt", "text-to-speech", "automatic-speech-recognition",
    "text-to-image", "text-to-video", "ocr",
}
# Extra id/note fragments for non-chat models whose kind field is unhelpful.
EXTRA_NON_CHAT = ("voxtral", "whisper", "transcribe", "-ocr", "ocr-",
                  "tts", "embed", "moderation", "diffusion", "flux", "sdxl")


def fetch():
    """Fetch the live catalog, trying each endpoint, then the local snapshot."""
    for url in CATALOG_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "modelhub-vibe/2"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            print(f"fetched {data.get('count', len(data.get('models', [])))} models from {url}")
            return data
        except Exception as e:
            print(f"fetch failed ({url}): {type(e).__name__}: {e}")
    if SNAPSHOT.exists():
        print(f"falling back to snapshot {SNAPSHOT}")
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    raise SystemExit("ERROR: no catalog source available")


def transform_models(raw):
    """Map engine /v1/models rows to modelhub's internal model format."""
    out, seen = [], set()
    disp_counts: dict[str, int] = {}
    for m in raw:
        if m.get("status") not in (None, "active"):
            continue
        gw = m.get("gateway")
        meta = PROVIDERS.get(gw)
        if not meta:
            continue
        mid = m.get("id") or m.get("provider_model_id")
        if not mid:
            continue
        key = (gw, mid)
        if key in seen:
            continue
        seen.add(key)
        hay = f"{m.get('id') or ''} {mid} {m.get('note') or ''} {m.get('display_name') or ''}".lower()
        if any(n in hay for n in NON_CHAT_NEEDLES) or any(n in hay for n in EXTRA_NON_CHAT):
            continue
        if (m.get("kind") or "").lower() in NON_CHAT_KINDS:
            continue
        inp = m.get("input_price_1m") or 0.0
        outp = m.get("output_price_1m") or 0.0
        if inp == 0 and outp == 0:
            free_kind = "tier" if m.get("free_kind") == "tier" else "free"
        else:
            free_kind = "cost"
        # Human label from the engine (note/display_name) when present,
        # e.g. id "mistral-large-latest" with note "Mistral Large 4".
        human = (m.get("display_name") or m.get("note") or "").strip()
        if human.startswith("[HUB]"):  # engine overlay rows: use the real name
            human = human[len("[HUB]"):].strip()
        # Notes that are just a vendor/org word carry no model label.
        stripped = clean_model_name(human) if human else ""
        if stripped.lower() in {"", "nvidia", "meta", "openai", "mistral", "qwen",
                                "google", "groq", "deepseek", "z.ai", "zhipu",
                                "anthropic", "xai", "bytedance", "alibaba",
                                "minimax", "moonshotai", "step", "baidu"}:
            stripped = ""
        name = stripped or clean_model_name(mid)
        disp = display_name_for(gw, name, free_kind, inp, outp)
        # Display names must be unique inside a picker.
        n = disp_counts.get(disp, 0) + 1
        disp_counts[disp] = n
        if n > 1:
            disp = f"{disp} ({n})"
        out.append({
            "apiId": mid,
            "provider": gw,
            "providerName": meta["name"],
            "baseUrl": m.get("base_url") or meta["base"],
            "keyEnv": meta["key"],
            "display": disp,
            "displayName": disp,
            "id": "custom:" + disp,
            "in": inp,
            "out": outp,
            "ctx": m.get("context_window") or 0,
            "maxout": m.get("max_completion_tokens") or 0,
            "tools": bool(m.get("tools_supported")),
            "img": bool(m.get("vision")),
            "freeKind": free_kind,
            "tier": m.get("tier"),
        })
    return out


def _strip_key_label(v: str) -> str:
    """Engine pools store LABEL:KEY; plain keys start with the key prefix.
    Strip a leading LABEL: only when what follows looks like a key."""
    v = v.strip().strip('"').strip("'")
    if ":" in v:
        label, rest = v.split(":", 1)
        # labels are short uppercase tags (USER1, LABEL_2, ...); keys are long
        if re.match(r"^[A-Z0-9_]{1,16}$", label) and len(rest) > 20:
            return rest.strip()
    return v


def load_keys(env_file):
    """KEY=VALUE env file. Accepts engine-style LABEL:KEY pools on any var;
    strips the label so adapters get the bare key."""
    keys = {}
    p = Path(env_file)
    if not p.exists():
        return keys
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        keys[k] = _strip_key_label(v)
        if k.endswith("_KEYS"):
            for part in v.strip().strip('"').strip("'").split(","):
                part = part.strip()
                if part:
                    keys.setdefault(k[:-len("_KEYS")] + "_API_KEY", _strip_key_label(part))
                    break
    return keys


def harvest_keys_from_settings() -> dict[str, list[str]]:
    """baseUrl -> [apiKey, ...] from the existing droid settings (the user's
    own config already stores per-endpoint keys; reuse them read-only)."""
    out: dict[str, list[str]] = {}
    p = Path.home() / ".factory" / "settings.json"
    if not p.exists():
        return out
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    for m in data.get("customModels") or []:
        b, k = m.get("baseUrl"), m.get("apiKey")
        if b and k and isinstance(k, str):
            k = _strip_key_label(k)
            if k not in out.setdefault(b, []):
                out[b].append(k)
    # proven keys from the working settings first, env-file keys after
    env_by_base: dict[str, list[str]] = {}
    for k, v in ENV_KEYS.items():
        meta = next((p2 for p2 in PROVIDERS.values() if p2["key"] == k), None)
        if meta:
            env_by_base.setdefault(meta["base"], []).append(v)
    for b, ks in env_by_base.items():
        for k in ks:
            if k not in out.setdefault(b, []):
                out[b].append(k)
    return out


def provider_direct_models(gateway: str, extra_keys: list[str]) -> dict[str, dict]:
    """Fetch <base>/models directly from the provider with every key we have
    for that endpoint. Returns id -> {"name": human name}."""
    meta = PROVIDERS.get(gateway)
    if not meta:
        return {}
    env_keys = [v for k, v in ENV_KEYS.items() if k == meta["key"]]
    keys = list(dict.fromkeys(env_keys + extra_keys))
    if not keys:
        return {}
    found: dict[str, dict] = {}
    for key in keys[:8]:
        try:
            req = urllib.request.Request(
                meta["base"].rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                doc = json.loads(resp.read().decode("utf-8"))
            rows = doc.get("data") if isinstance(doc, dict) else doc
            for r in rows or []:
                rid = r.get("id")
                if rid and rid not in found:
                    found[rid] = {"name": r.get("name") or rid}
        except Exception:
            continue
    return found


ENV_KEYS: dict[str, str] = {}


def merge_provider_direct(models: list[dict]) -> list[dict]:
    """For each gateway, add engine-catalog rows that are routed under another
    gateway but actually belong to this provider's endpoint (matched by the
    engine row's provider_base_url), plus provider-direct-only models."""
    by_base = harvest_keys_from_settings()
    have = {(m["provider"], m["apiId"]) for m in models}
    # engine rows by apiId, for price/limit enrichment
    engine_by_id: dict[str, dict] = {}
    for m in models:
        engine_by_id.setdefault(m["apiId"], m)
    # provider_base_url per apiId from the raw catalog is not in `models`;
    # re-derive from the last fetch if available.
    added = 0
    disp_counts: dict[str, int] = {}
    for m in models:
        disp_counts[m["display"]] = disp_counts.get(m["display"], 0) + 1
    for gw, meta in sorted(PROVIDERS.items()):
        direct = provider_direct_models(gw, by_base.get(meta["base"], []))
        if not direct:
            continue
        # Collapse provider aliases: same human name, multiple ids — keep the
        # canonical one ("-latest" wins over dated/-4/-0 variants).
        name_to_ids: dict[str, list[str]] = {}
        for rid, info in direct.items():
            nm = (info.get("name") or "").strip().lower()
            if nm:
                name_to_ids.setdefault(nm, []).append(rid)
        alias_drop: set[str] = set()
        for nm, ids in name_to_ids.items():
            if len(ids) < 2:
                continue
            canon = sorted(ids, key=lambda r: (0 if r.endswith("-latest") else 1, len(r), r))[0]
            alias_drop.update(i for i in ids if i != canon)
        for rid, info in direct.items():
            if rid in alias_drop:
                continue
            if (gw, rid) in have:
                continue
            hay = rid.lower()
            if any(n in hay for n in NON_CHAT_NEEDLES) or any(n in hay for n in EXTRA_NON_CHAT):
                continue
            # Only add if the engine also knows this id (routed elsewhere or
            # missing from this gateway) — provider-only lists without an
            # engine row lack pricing and get skipped.
            eng = engine_by_id.get(rid)
            if eng is None:
                continue
            inp = eng.get("in", 0.0) or 0.0
            outp = eng.get("out", 0.0) or 0.0
            if inp == 0 and outp == 0:
                fk = "tier" if eng.get("tier") == "free_tier" else "free"
            else:
                fk = "cost"
            # Human name from the provider ("mistral-large-4" -> "Mistral Large 4")
            # is only used when it names an actual model, not just the vendor.
            name = (info.get("name") or "").strip()
            low = name.lower()
            if low in {"mistral", "openai", "nvidia", "meta", "z.ai", "zhipu",
                       "qwen", "google", "groq", "deepseek", "anthropic", "xai"}:
                name = ""
            if not name:
                name = clean_model_name(rid)
            if re.fullmatch(r"[a-z0-9]+(-[a-z0-9.]+)+", name):
                name = name.replace("-", " ").title()
            disp = display_name_for(gw, name, fk, inp, outp)
            n = disp_counts.get(disp, 0) + 1
            disp_counts[disp] = n
            if n > 1:
                disp = f"{disp} ({n})"
            models.append({
                "apiId": rid,
                "provider": gw,
                "providerName": meta["name"],
                "baseUrl": meta["base"],
                "keyEnv": meta["key"],
                "display": disp,
                "displayName": disp,
                "id": "custom:" + disp,
                "in": inp,
                "out": outp,
                "ctx": eng.get("ctx") or 0,
                "maxout": eng.get("maxout") or 0,
                "tools": bool(eng.get("tools", True)),
                "img": bool(eng.get("img")),
                "freeKind": fk,
                "tier": eng.get("tier"),
            })
            added += 1
    if added:
        print(f"provider-direct merge: +{added} models")
    return models


def run_apply(models, keys, apps, yes):
    ns = argparse.Namespace(profile="vibe", apps=apps, yes=yes)
    return cmd_apply(ns, models, keys)


def ssh(cmd, stdin=None, timeout=120):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, cmd],
        input=stdin, text=True, capture_output=True, timeout=timeout,
    )


def push_to_engine(models, apps, yes):
    """Copy package + script + model list to the engine, then apply remotely."""
    print("\n=== pushing to Hetzner engine (ssh engine) ===")
    pkg = Path("/home/flintx/modelhub")
    r = ssh("mkdir -p /root/modelhub /root/.local/share/modelhub-vibe /root/.config/modelhub")
    if r.returncode != 0:
        print(f"ERROR: engine unreachable: {r.stderr.strip()}")
        return 1
    tar = subprocess.run(
        f"tar czf - -C {pkg.parent} modelhub "
        "--exclude=__pycache__ --exclude=backups --exclude='*.bak*' --exclude='*.old' | "
        f"ssh -o BatchMode=yes -o ConnectTimeout=10 {SSH_HOST} 'tar xzf - -C /root'",
        shell=True, capture_output=True, text=True, timeout=300,
    )
    if tar.returncode != 0:
        print(f"ERROR: package upload failed: {tar.stderr.strip()}")
        return 1
    print("uploaded modelhub package to /root/modelhub")

    payload = json.dumps({"models": models}, ensure_ascii=False)
    r = ssh(f"cat > {REMOTE_MODELS}", stdin=payload, timeout=180)
    if r.returncode != 0:
        print(f"ERROR: model upload failed: {r.stderr.strip()}")
        return 1
    print(f"uploaded {len(models)} models to {REMOTE_MODELS}")

    r = subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         str(Path(__file__).resolve()), f"{SSH_HOST}:/root/.local/share/modelhub-vibe/vibe_sync.py"],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"ERROR: script upload failed: {r.stderr.strip()}")
        return 1

    # Regenerate the engine-side key file from the engine's own key pools
    # (values never leave the engine; only file names are involved here).
    gen_env = r'''
import re, os
src = "/root/hetzner/ai-engine/.env"
dst = "/root/.config/modelhub/env"
lines = []
if os.path.exists(dst):
    lines = [l for l in open(dst).read().splitlines()
             if l.strip() and not l.startswith("#") and "modelhub-vibe" not in l]
lines.append("# generated by modelhub-vibe from /root/hetzner/ai-engine/.env")
if os.path.exists(src):
    for l in open(src):
        m = re.match(r"^([A-Z0-9_]+_KEYS)=(.*)$", l.strip())
        if not m:
            continue
        name, val = m.group(1), m.group(2).strip().strip('"').strip("'")
        first = val.split(",")[0].split(":")[-1].strip()
        if first:
            lines.append(f"{name[:-len('_KEYS')]}_API_KEY={first}  # modelhub-vibe")
with open(dst, "w") as f:
    f.write("\n".join(lines) + "\n")
os.chmod(dst, 0o600)
print(f"env keys written: {sum(1 for l in lines if l.startswith('#') is False and '=' in l and not l.startswith('#'))}")
'''
    r = ssh("python3 -", stdin=gen_env)
    print(r.stdout.strip() or r.stderr.strip())

    flag = "" if yes else " --dry-run"
    r = ssh(
        f"cd /root/modelhub && HOME=/root python3 "
        f"/root/.local/share/modelhub-vibe/vibe_sync.py --on-engine --apps {apps}{flag}",
        timeout=600,
    )
    print(r.stdout)
    if r.stderr.strip():
        print(r.stderr, file=sys.stderr)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(prog="modelhub-vibe",
                                 description="sync live engine catalog to local apps + Hetzner engine")
    ap.add_argument("--url", help="override catalog URL")
    ap.add_argument("--snapshot", help="use a local catalog JSON file instead of fetching")
    ap.add_argument("--apps", help="comma-separated apps (default: all registered)")
    ap.add_argument("--dry-run", action="store_true", help="plan only, write nothing")
    ap.add_argument("--no-engine", action="store_true", help="skip the engine push")
    ap.add_argument("--save-list", metavar="FILE",
                    help="save all models grouped by provider (with prices) to this txt file")
    ap.add_argument("--on-engine", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    from lib.banner import print_banner
    print_banner()

    apps = args.apps or ",".join(REGISTRY.keys())
    yes = not args.dry_run

    if args.on_engine:
        # Running on the engine itself: models were uploaded by the local run.
        p = Path(REMOTE_MODELS)
        if not p.exists():
            print(f"ERROR: {p} missing; run modelhub-vibe on the local machine first")
            return 1
        models = json.loads(p.read_text(encoding="utf-8"))["models"]
        keys = load_keys(ENGINE_ENV)
        # Only target apps whose config actually exists on this host.
        import modelhub as hub
        wanted = [a.strip() for a in apps.split(",") if a.strip()]
        existing = []
        for a in wanted:
            if a not in REGISTRY:
                print(f"{a}: no adapter on this host, skipped")
                continue
            files = hub.APP_FILES.get(a, [])
            if files and not any(f.exists() for f in files):
                print(f"{a}: no config on this host, skipped")
                continue
            existing.append(a)
        if not existing:
            print("nothing to apply on this host")
            return 0
        print(f"engine apply: {len(models)} models, apps={','.join(existing)}, "
              f"keys={len(keys)}, yes={yes}")
        return run_apply(models, keys, ",".join(existing), yes)

    if args.snapshot:
        data = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        print(f"using snapshot {args.snapshot}")
    else:
        if args.url:
            global CATALOG_URLS
            CATALOG_URLS = [args.url] + CATALOG_URLS
        data = fetch()

    models = transform_models(data.get("models", []))
    if not models:
        print("ERROR: no usable models after transform")
        return 1
    print(f"transformed: {len(models)} models across "
          f"{len({m['provider'] for m in models})} gateways")

    keys = load_keys(Path.home() / ".config" / "modelhub" / "env")
    ENV_KEYS.clear()
    ENV_KEYS.update(keys)
    print(f"local keys: {len(keys)}   apps: {apps}   yes: {yes}")
    models = merge_provider_direct(models)
    print(f"after provider-direct merge: {len(models)} models across "
          f"{len({m['provider'] for m in models})} gateways")

    if args.save_list:
        from lib.banner import save_list
        p = save_list(models, args.save_list)
        print(f"saved model list -> {p}")

    rc = run_apply(models, keys, apps, yes)

    from lib.banner import report
    applied = []
    if rc == 0:
        from modelhub import build_plans, is_pending
        for p in build_plans(models, keys, [a.strip() for a in apps.split(",") if a.strip()]):
            if p.files and p.stats.get("managed"):
                applied.append((p.label, p.stats["managed"]))
    report(applied, models)

    if rc == 0 and not args.no_engine:
        rc = push_to_engine(models, apps, yes) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
