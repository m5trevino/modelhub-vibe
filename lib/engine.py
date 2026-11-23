"""Remote engine target (Hetzner) for modelhub.

Phase 1 manages the five gateways the engine already routes:
openrouter, novita, xkiro, merge, ollama. Groq and Hetzner are kept as-is.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

SSH = "engine"
REMOTE = "/root/hetzner/ai-engine"
OVERLAY = f"{REMOTE}/modelhub_models.json"
KEEP = {"groq", "hetzner"}
MANAGED = {"openrouter", "novita", "xkiro", "merge", "ollama"}


def engine_id(model: dict) -> str:
    """Match the engine's Ollama naming convention."""
    api_id = model["apiId"]
    if model["provider"] == "ollama":
        return api_id + ("-cloud" if ":" in api_id else ":cloud")
    return api_id


def build_overlay(models: list[dict]) -> dict:
    rows = []
    seen = set()
    for m in models:
        if m["provider"] not in MANAGED:
            continue
        mid = engine_id(m)
        key = (m["provider"], mid)
        if key in seen:
            continue
        seen.add(key)
        ctx = m.get("ctx")
        out_cap = m.get("maxout") or ctx
        rows.append({
            "id": mid,
            "gateway": m["provider"],
            "note": f"[HUB] {m['display']}",
            "status": "active",
            "context_window": int(ctx) if ctx else None,
            "max_completion_tokens": int(out_cap) if out_cap else None,
            "input_price_1m": float(m.get("in") or 0.0),
            "output_price_1m": float(m.get("out") or 0.0),
            "tools_supported": bool(m.get("tools") is True),
            "display_name": m["display"],
        })
    rows.sort(key=lambda r: (r["gateway"], r["id"].lower()))
    return {
        "generated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "modelhub",
        "keep_gateways": sorted(KEEP),
        "models": rows,
    }


def ssh(cmd: str, stdin: str | None = None, timeout: int = 60):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH, cmd],
        input=stdin, text=True, capture_output=True, timeout=timeout,
    )


def fetch_registry() -> list[dict]:
    code = (
        "import sys,json;sys.path.insert(0,'.');"
        "import app.config as c;"
        "print(json.dumps([{'id':m.id,'gateway':m.gateway,'ip':m.input_price_1m,"
        "'op':m.output_price_1m,'ctx':m.context_window,'tools':m.tools_supported} "
        "for m in c.MODEL_REGISTRY]))"
    )
    r = ssh(f"cd {REMOTE} && python3 -c \"{code}\"")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    line = [x for x in r.stdout.strip().splitlines() if x.startswith("[")][-1]
    return json.loads(line)


def _health() -> dict:
    r = ssh("curl -s --max-time 5 http://127.0.0.1:3099/health")
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


def _models_count() -> int:
    r = ssh("curl -s --max-time 10 http://127.0.0.1:3099/v1/models")
    if r.returncode != 0:
        return -1
    try:
        doc = json.loads(r.stdout)
        return len(doc.get("models") or doc.get("data") or [])
    except json.JSONDecodeError:
        return -1


PATCH = r'''
from pathlib import Path
p = Path("/root/hetzner/ai-engine/app/config.py")
s = p.read_text()
if "# MODELHUB OVERLAY" in s:
    print("already patched")
    raise SystemExit(0)
anchor = "\n# Apply Status Overrides"
if anchor not in s:
    print("anchor missing")
    raise SystemExit(2)
block = r"""
# MODELHUB OVERLAY
try:
    _hub_path = os.path.join(os.path.dirname(__file__), "..", "modelhub_models.json")
    if os.path.exists(_hub_path):
        with open(_hub_path, "r") as _hub_f:
            _hub = json.load(_hub_f)
        _hub_models = _hub.get("models") or []
        _hub_keep = set(_hub.get("keep_gateways") or ["groq", "hetzner"])
        if len(_hub_models) >= 50:
            _hub_new = []
            for _hm in _hub_models:
                try:
                    _hub_new.append(ModelConfig(**_hm))
                except Exception as _hub_model_err:
                    print(f"[modelhub] skip {_hm.get('id')}: {_hub_model_err}")
            if len(_hub_new) >= max(1, int(len(_hub_models) * 0.8)):
                _hub_kept = [m for m in MODEL_REGISTRY if m.gateway in _hub_keep]
                MODEL_REGISTRY[:] = _hub_kept + _hub_new
                print(f"[modelhub] registry replaced: {len(_hub_kept)} kept + {len(_hub_new)} hub = {len(MODEL_REGISTRY)}")
            else:
                print(f"[modelhub] validation failed ({len(_hub_new)}/{len(_hub_models)}); registry unchanged")
except Exception as _hub_err:
    print(f"[modelhub] overlay error: {_hub_err}")
"""
s = s.replace(anchor, "\n" + block + anchor, 1)
tmp = p.with_suffix(".py.tmp")
tmp.write_text(s)
tmp.replace(p)
print("patched")
'''

PRUNE = r'''
import json
p = "/root/hetzner/ai-engine/config/runtime_config.json"
d = json.load(open(p))
prov = d.get("providers")
allowed = {"groq", "hetzner", "openrouter", "novita", "xkiro", "merge", "ollama"}
if isinstance(prov, dict):
    before = len(prov)
    d["providers"] = {k: v for k, v in prov.items() if k in allowed}
    with open(p, "w") as f:
        json.dump(d, f, indent=2)
    print(f"providers {before}->{len(d['providers'])}")
else:
    print("providers key missing; skipped")
'''

PATCH_STORE = (Path(__file__).with_name("engine_patch_store.py")).read_text()
PATCH_MAIN = (Path(__file__).with_name("engine_patch_main.py")).read_text()


def plan(models: list[dict]) -> int:
    overlay = build_overlay(models)
    current = fetch_registry()
    by_gw: dict[str, int] = {}
    for m in current:
        by_gw[m["gateway"]] = by_gw.get(m["gateway"], 0) + 1
    keep = sum(n for g, n in by_gw.items() if g in KEEP)
    removed = len(current) - keep
    overlay_ids = {(m["gateway"], m["id"]) for m in overlay["models"]}
    current_ids = {(m["gateway"], m["id"]) for m in current}
    overlap = len(overlay_ids & current_ids)
    new = len(overlay_ids - current_ids)
    total_after = keep + len(overlay["models"])

    print(f"engine: {SSH}:{REMOTE}")
    print(f"current registry: {len(current)}")
    print(f"  keep (groq/hetzner): {keep}")
    print(f"  remove: {removed}")
    print(f"overlay: {len(overlay['models'])} models")
    print(f"  replace existing: {overlap}")
    print(f"  net new: {new}")
    print(f"registry after apply: {total_after}")
    print("\noverlay by gateway:")
    counts: dict[str, int] = {}
    for m in overlay["models"]:
        counts[m["gateway"]] = counts.get(m["gateway"], 0) + 1
    for g in sorted(counts):
        print(f"  {g:12} {counts[g]:4}")
    print("\nNo files were written.")
    return 0


def apply(models: list[dict], yes: bool) -> int:
    overlay = build_overlay(models)
    if not overlay["models"]:
        print("no models selected for the engine")
        return 1
    if not yes:
        print(f"dry run: would write {len(overlay['models'])} models to {SSH}")
        print("re-run with --yes")
        return 0

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup = f"{REMOTE}/backups/modelhub-{ts}"
    text = json.dumps(overlay, indent=2, ensure_ascii=False)

    def run(cmd: str, stdin: str | None = None, timeout: int = 90):
        r = ssh(cmd, stdin=stdin, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
        return r

    try:
        run(f"cd {REMOTE} && mkdir -p {backup} && cp -a app/config.py app/core/config_store.py app/main.py dynamic_models.json config/runtime_config.json .env {backup}/")
        print(f"backup: {backup}")
        run(f"cat > {OVERLAY}", stdin=text, timeout=180)
        print(f"uploaded overlay: {len(overlay['models'])} models")
        r = ssh("python3 -", stdin=PATCH)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError("config patch failed")
        r = ssh("python3 -", stdin=PATCH_STORE)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError("config_store patch failed")
        r = ssh("python3 -", stdin=PATCH_MAIN)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError("main patch failed")
        run(f"cd {REMOTE} && python3 -m json.tool modelhub_models.json >/dev/null && python3 -m py_compile app/config.py && echo '[]' > dynamic_models.json")
        print("validated config and cleared dynamic_models.json")
        r = ssh("python3 -", stdin=PRUNE)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            raise RuntimeError("provider prune failed")
        run("systemctl restart peacock-engine", timeout=60)
        print("restarted peacock-engine")

        ok = False
        for _ in range(30):
            h = _health()
            if h.get("status") == "ONLINE":
                ok = True
                break
            import time
            time.sleep(2)
        if not ok:
            raise RuntimeError("engine did not return ONLINE")
        count = _models_count()
        print(f"health: ONLINE")
        print(f"/v1/models: {count}")
        print(f"registry: {len(overlay['models'])} hub models + groq/hetzner")
        return 0
    except Exception as e:
        print(f"FAILED: {e}")
        print("restoring backup...")
        try:
            ssh(f"cd {REMOTE} && cp -a {backup}/config.py app/config.py && cp -a {backup}/config_store.py app/core/config_store.py && cp -a {backup}/main.py app/main.py && cp -a {backup}/dynamic_models.json dynamic_models.json && cp -a {backup}/runtime_config.json config/runtime_config.json && cp -a {backup}/.env .env && systemctl restart peacock-engine", timeout=60)
            print("restored and restarted")
        except Exception as restore_err:
            print(f"restore failed: {restore_err}")
        return 1


def status() -> int:
    h = _health()
    count = _models_count()
    print(f"engine: {SSH}:{REMOTE}")
    print(f"health: {h.get('status', 'unknown')}")
    print(f"/v1/models: {count}")
    try:
        current = fetch_registry()
        by_gw: dict[str, int] = {}
        for m in current:
            by_gw[m["gateway"]] = by_gw.get(m["gateway"], 0) + 1
        print(f"registry: {len(current)}")
        for g in sorted(by_gw):
            print(f"  {g:12} {by_gw[g]:4}")
    except Exception as e:
        print(f"registry read failed: {e}")
    r = ssh(f"ls -l {OVERLAY} 2>/dev/null")
    print(r.stdout.strip() or "overlay: missing")
    return 0


def rollback(to: str | None = None) -> int:
    if to:
        backup = f"{REMOTE}/backups/modelhub-{to}"
    else:
        r = ssh(f"ls -1d {REMOTE}/backups/modelhub-* 2>/dev/null | sort | tail -1")
        backup = r.stdout.strip()
    if not backup:
        print("no engine backup found")
        return 1
    print(f"restoring {backup}")
    r = ssh(
        f"cd {REMOTE} && cp -a {backup}/config.py app/config.py && "
        f"cp -a {backup}/config_store.py app/core/config_store.py && "
        f"cp -a {backup}/main.py app/main.py && "
        f"cp -a {backup}/dynamic_models.json dynamic_models.json && "
        f"cp -a {backup}/runtime_config.json config/runtime_config.json && "
        f"cp -a {backup}/.env .env && systemctl restart peacock-engine",
        timeout=60,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        return 1
    print("restored and restarted")
    return 0
