#!/usr/bin/env python3
"""modelhub — keep local AI coding apps stocked with free provider models.

Commands:
  refresh   pull all provider catalogs and rebuild the registry
  plan      read-only: show what would change per app
  apply     write managed entries (requires --yes)
  status    sync state per app
  doctor    environment and config checks
  list      print the selected model set
  run       launch an app with the modelhub key environment
  rollback  restore an app from a timestamped backup
  sync-from-engine  fetch models from Peacock engine and sync to all apps
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

from lib import safety
from lib import engine
from lib import launcher
from lib.adapters import REGISTRY, TIER1, TIER2
from lib.adapters.base import Plan
from lib.catalog import ENV_FILE, PROFILES, build_models, load_catalog, load_keys, summarize

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state" / "last_run.json"

APP_FILES = {
    "droid": [Path.home() / ".factory" / "settings.json"],
    "hermes": [Path.home() / ".hermes" / "config.yaml"],
    "opencode": [Path.home() / ".config" / "opencode" / "opencode.jsonc"],
    "kimchi": [
        Path.home() / ".config" / "kimchi" / "harness" / "models.json",
        Path.home() / ".config" / "kimchi" / "harness" / "settings.json",
        Path.home() / ".config" / "kimchi" / "harness" / "auth.json",
    ],
    "goose": [
        Path.home() / ".config" / "goose" / "config.yaml",
        Path.home() / ".config" / "modelhub" / "goose.env",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_openrouter.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_xkiro.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_merge.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_septorlabs.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_airforce.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_novita.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_deepinfra.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_ollama.json",
        Path.home() / ".config" / "goose" / "custom_providers" / "custom_hetzner.json",
    ],
    "qwen": [Path.home() / ".qwen" / "settings.json"],
    "pi": [Path.home() / ".pi" / "agent" / "models.json"],
    "kilo": [Path.home() / ".config" / "kilo" / "kilo.jsonc"],
}

BINARIES = {
    "droid": "droid",
    "hermes": "hermes",
    "opencode": "opencode",
    "kimchi": "kimchi",
    "goose": "goose",
    "qwen": "qwen",
    "pi": "pi-dev",
    "kilo": str(Path.home() / ".kilo" / "bin" / "kilo"),
}


def apps_from(args) -> list[str]:
    if getattr(args, "apps", None):
        return [a.strip() for a in args.apps.split(",") if a.strip()]
    return list(REGISTRY)


def build_plans(models, keys, apps) -> list[Plan]:
    plans = []
    for app in apps:
        mod = REGISTRY.get(app)
        if mod is None:
            plans.append(Plan(app=app, label=app, warnings=[f"unknown app: {app}"]))
            continue
        try:
            plans.append(mod.build(models, keys))
        except Exception as e:  # never let one adapter stop the rest
            plans.append(Plan(app=app, label=app, warnings=[f"ERROR {type(e).__name__}: {e}"]))
    return plans


def is_pending(plan: Plan) -> bool:
    for f in plan.files:
        if f.delete:
            if f.path.exists():
                return True
            continue
        if not f.path.exists():
            return True
        try:
            if f.path.read_text(encoding="utf-8") != f.content:
                return True
        except OSError:
            return True
    return False


def _refs(doc: dict) -> list[str]:
    refs = []
    def add(container, key):
        if isinstance(container, dict):
            v = container.get(key)
            if isinstance(v, str) and v:
                refs.append(v)
    add(doc.get("sessionDefaultSettings"), "model")
    add(doc.get("sessionDefaultSettings"), "specModeModel")
    add(doc, "specModeModel")
    add(doc.get("subagentModelSettings"), "lightModel")
    add(doc.get("subagentModelSettings"), "mediumModel")
    add(doc.get("subagentModelSettings"), "heavyModel")
    add(doc.get("missionModelSettings"), "workerModel")
    add(doc.get("missionModelSettings"), "validationWorkerModel")
    add(doc, "imageGenerationModel")
    return refs


def guard_droid(plan: Plan) -> None:
    """Refuse to drop a model that is currently referenced by Droid."""
    path = plan.files[0].path
    old = json.loads(path.read_text(encoding="utf-8"))
    new = json.loads(plan.files[0].content)
    old_ids = {m.get("id") for m in old.get("customModels") or [] if m.get("id")}
    new_ids = {m.get("id") for m in new.get("customModels") or [] if m.get("id")}
    lost = [r for r in _refs(old) if r in old_ids and r not in new_ids]
    invalid = [r for r in _refs(new) if r.startswith("custom:") and r not in new_ids]
    if lost:
        raise RuntimeError("would drop referenced model(s): " + ", ".join(lost))
    if invalid:
        raise RuntimeError("would leave dangling reference(s): " + ", ".join(invalid))


def cmd_plan(args, models, keys):
    plans = build_plans(models, keys, apps_from(args))
    print(f"profile: {args.profile}   models: {len(models)}")
    print(f"{'APP':24} {'MANAGED':>7} {'REMOVED':>7} {'FILES':>5}  STATE")
    print("-" * 66)
    for p in plans:
        managed = p.stats.get("managed", 0)
        removed = p.stats.get("removed", 0)
        state = "pending" if is_pending(p) else "in sync"
        print(f"{p.label[:23]:24} {managed:>7} {removed:>7} {len(p.files):>5}  {state}")
        for w in p.warnings:
            print(f"    ! {w}")
    print("\nNo files were written. Run `modelhub apply --yes` to apply.")
    return 0


def cmd_apply(args, models, keys):
    plans = build_plans(models, keys, apps_from(args))
    todo = [p for p in plans if p.files and is_pending(p)]
    errors = [p for p in plans if any(w.startswith("ERROR") for w in p.warnings)]

    for p in errors:
        for w in p.warnings:
            print(f"{p.app}: {w}")
    if errors:
        print("aborting: adapter errors")
        return 1
    for p in todo:
        if p.app == "droid":
            try:
                guard_droid(p)
            except Exception as e:
                print(f"aborting: {e}")
                return 1
    if not todo:
        print("everything is already in sync")
        return 0
    if not args.yes:
        print("dry run: this would change " + ", ".join(p.app for p in todo))
        print("re-run with --yes to write")
        return 0

    ts = safety.stamp()
    applied = []
    for p in todo:
        backups = []
        try:
            for f in p.files:
                b = safety.backup(f.path, ts)
                if b:
                    f._backup_path = b
                backups.append((f, b))
                if f.delete:
                    if f.path.exists():
                        f.path.unlink()
                else:
                    safety.atomic_write(f.path, f.content, f.mode)
            for f in p.files:
                if f.delete:
                    continue
                if f.fmt != "env":
                    safety.validate(f.path, f.fmt)
            applied.append(p)
            print(f"applied {p.label}: {p.stats.get('managed', 0)} models")
            for w in p.warnings:
                print(f"    ! {w}")
        except Exception as e:
            for f, b in backups:
                if b:
                    safety.restore(f.path, b)
                elif f.path.exists():
                    f.path.unlink()
            print(f"FAILED {p.label}: {type(e).__name__}: {e} (rolled back)")
            return 1

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "timestamp": ts,
        "profile": args.profile,
        "apps": [p.app for p in applied],
        "models": len(models),
        "backups": [str(b) for p in applied for f, b in
                    [(f, getattr(f, '_backup_path', None)) for f in p.files] if b],
    }, indent=2) + "\n")
    seen = []
    for p in applied:
        for f in p.files:
            b = getattr(f, "_backup_path", None)
            if b and str(b) not in seen:
                seen.append(str(b))
    if seen:
        print("\nbackups (next to each original):")
        for s in seen:
            print(f"  {s}")
    return 0


def cmd_status(args, models, keys):
    plans = build_plans(models, keys, apps_from(args))
    print(f"profile: {args.profile}   catalog: {len(models)} models")
    for p in plans:
        state = "PENDING" if is_pending(p) else "in sync"
        print(f"  {p.label:24} {state:8} managed={p.stats.get('managed', 0)}")
    if STATE.exists():
        s = json.loads(STATE.read_text())
        print(f"\nlast apply: {s.get('timestamp')}  apps={', '.join(s.get('apps', []))}")
        print(f"last backup: {s.get('backup')}")
    else:
        print("\nno apply recorded yet")
    return 0


def cmd_list(args, models, keys):
    for m in models:
        price = "free" if m["freeKind"] == "free" else m["freeKind"]
        caps = ("T" if m.get("tools") is True else "-") + ("I" if m.get("img") is True else "-")
        print(f"{m['provider']:12} {m['apiId'][:58]:58} {price:5} {caps}  {m['display']}")


def cmd_doctor(args, models, keys):
    errors, warns = [], []
    cat = load_catalog()
    print(f"catalog: {cat.get('generated')}  rows={len(cat.get('models', []))}  free={summarize(build_models('all-free', cat))['total']}")

    if not ENV_FILE.exists():
        errors.append(f"key store missing: {ENV_FILE}")
    else:
        mode = oct(ENV_FILE.stat().st_mode & 0o777)
        if mode != "0o600":
            warns.append(f"key store mode is {mode}, expected 600")
        for p in ("OPENROUTER_API_KEY", "XKIRO_API_KEY", "MERGE_API_KEY", "SEPTORLABS_API_KEY", "AIRFORCE_API_KEY"):
            if not keys.get(p):
                warns.append(f"missing key: {p}")

    for app, paths in APP_FILES.items():
        for path in paths:
            if not path.exists():
                warns.append(f"{app}: missing {path}")
                continue
            if path.suffix == ".env" or path.name.endswith(".env"):
                continue
            fmt = "yaml" if path.suffix in (".yaml", ".yml") else ("jsonc" if path.suffix == ".jsonc" else "json")
            try:
                safety.validate(path, fmt)
            except Exception as e:
                errors.append(f"{app}: {path} does not parse: {e}")

    droid_path = APP_FILES["droid"][0]
    if droid_path.exists():
        d = json.loads(droid_path.read_text())
        cms = d.get("customModels") or []
        ids = [m.get("id") for m in cms if m.get("id")]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            warns.append(f"droid: duplicate ids: {len(dupes)}")
        refs = [d.get("specModeModel"), (d.get("sessionDefaultSettings") or {}).get("model")]
        for key, val in (d.get("subagentModelSettings") or {}).items():
            if key.endswith("Model"):
                refs.append(val)
        for key, val in (d.get("missionModelSettings") or {}).items():
            if key.endswith("Model"):
                refs.append(val)
        dangling = [r for r in refs if r and r not in set(ids)]
        if dangling:
            warns.append(f"droid: dangling model refs: {len(dangling)}")

    pi_wrapper = Path("/usr/local/bin/pi-dev")
    if pi_wrapper.exists():
        text = pi_wrapper.read_text(errors="ignore")
        if "/home/flintx/projects/pi-src/pi" in text and not Path("/home/flintx/projects/pi-src/pi").exists():
            warns.append("pi: launcher cd's into a missing directory")

    if not APP_FILES["kilo"][0].exists():
        warns.append("kilo: no config yet (apply will create it)")

    for w in warns:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    if not warns and not errors:
        print("clean")
    return 1 if errors else 0


def cmd_refresh(args, models, keys):
    env = os.environ.copy()
    env.update(keys)
    alias = {
        "MERGE_KEY": "MERGE_API_KEY",
        "OPENROUTER_KEY": "OPENROUTER_API_KEY",
        "XKIRO_KEY": "XKIRO_API_KEY",
        "OLLAMA_KEY": "OLLAMA_API_KEY",
        "NOVITA_KEY": "NOVITA_API_KEY",
        "CLOD_KEY": "CLOD_API_KEY",
        "CEREBRAS_KEY": "CEREBRAS_API_KEY",
        "EXPERIENTIAL_KEY": "EXPERIENTIALLABS_API_KEY",
        "SAIL_KEY": "SAILRESEARCH_API_KEY",
        "ROUTER9_KEY": "ROUTER9_API_KEY",
        "SEPT_KEY": "SEPTORLABS_API_KEY",
        "AIRFORCE_KEY": "AIRFORCE_API_KEY",
        "DEEPINFRA_KEY": "DEEPINFRA_API_KEY",
    }
    for target, src in alias.items():
        env[target] = env.get(src, "")

    print("refreshing provider catalogs...")
    r = subprocess.run([sys.executable, "/home/flintx/provider-models/fetch.py"], env=env)
    if r.returncode != 0:
        return r.returncode
    print("rebuilding registry...")
    r = subprocess.run([sys.executable, "/home/flintx/model-catalog-site/build_data.py"], env=env)
    return r.returncode


def cmd_run(args, models, keys):
    app = args.app
    binary = BINARIES.get(app)
    if not binary:
        print(f"unknown app: {app}")
        return 1
    exe = shutil.which(binary) or (binary if Path(binary).exists() else None)
    if not exe:
        print(f"binary not found: {binary}")
        return 1
    env = os.environ.copy()
    env.update(keys)
    if app == "goose":
        g = Path.home() / ".config" / "modelhub" / "goose.env"
        if g.exists():
            for line in g.read_text().splitlines():
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k] = v
    os.execvpe(exe, [exe] + args.rest, env)


def cmd_rollback(args, models, keys):
    ts = args.to
    root = ROOT / "backups" / ts
    if not root.exists():
        print(f"no backup at {root}")
        return 1
    restored = 0
    for path in APP_FILES.get(args.app, []):
        if not path.exists() and not (root / safety._rel(path)).exists():
            continue
        dest = root / safety._rel(path)
        if dest.exists():
            safety.restore(path, dest)
            restored += 1
            print(f"restored {path}")
    if not restored:
        print("nothing restored")
        return 1
    return 0


def cmd_sync(args, keys):
    """Refresh catalogs, then write every app. This is the bare `modelhub` path."""
    if not getattr(args, "skip_refresh", False):
        print("=== refresh ===")
        rc = cmd_refresh(args, [], keys)
        if rc != 0:
            print("refresh failed; applying the last good catalog")

    catalog = load_catalog()
    models = build_models(args.profile, catalog)
    print(f"\n=== apply ({len(models)} models) ===")
    args.apps = getattr(args, "apps", None)
    args.yes = True
    rc = cmd_apply(args, models, keys)
    if rc == 0:
        print("\n=== status ===")
        cmd_status(args, models, keys)
    return rc


def cmd_live(args, keys):
    """Catalog live: one fetch of the engine's /v1/vibe, apps use real provider gateways."""
    sys.modules.setdefault("modelhub", sys.modules[__name__])  # share this module with vibe_sync
    import vibe_sync
    return vibe_sync.run(getattr(args, "apps", None), bool(getattr(args, "yes", False)))


def cmd_sync_from_engine(args, keys):
    """Fetch models from Peacock engine and sync to all apps (local + Hetzner Droid)."""
    import urllib.request
    import json
    
    # Fetch models from the engine (respecting catalog policy)
    # Try local engine first, then fall back to public URL
    engine_urls = [
        "http://engine:3099/v1/models?respect_policy=true",
        "https://engine.save-aichats.com/v1/models?respect_policy=true",
    ]
    engine_models = []
    for url in engine_urls:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                engine_models = data.get("models") or data.get("data") or []
                break
        except Exception as e:
            print(f"Trying next URL... ({e})")
            continue
    
    if not engine_models:
        print("Error: Could not fetch models from engine.")
        return 1
    
    if not engine_models:
        print("No models fetched from engine.")
        return 1
    
    print(f"Fetched {len(engine_models)} models from engine.")
    
    # Import PROVIDERS from catalog
    from lib.catalog import PROVIDERS
    
    # Get list of providers with keys
    providers_with_keys = {k.split("_")[0].lower() for k in keys.keys()}
    
    # Convert engine model format to modelhub format
    models = []
    skipped = 0
    for m in engine_models:
        # Skip non-active models
        if m.get("status") != "active":
            continue
        
        provider = m.get("gateway")
        # Skip providers without keys
        if provider not in providers_with_keys:
            skipped += 1
            continue
        
        # Get provider metadata (baseUrl, keyEnv)
        meta = PROVIDERS.get(provider)
        if not meta:
            skipped += 1
            continue
        
        # Map engine model fields to modelhub format
        display_name = m.get("display_name") or m.get("note") or m.get("id")
        price_tag = ""
        in_price = m.get("input_price_1m") or 0.0
        out_price = m.get("output_price_1m") or 0.0
        
        if in_price > 0 or out_price > 0:
            price_tag = f"[COST {in_price}/{out_price}] "
        elif m.get("free_kind") == "tier":
            price_tag = "[FREE TIER] "
        elif m.get("free") or in_price == 0 and out_price == 0:
            price_tag = "[FREE] "
        
        model_dict = {
            "apiId": m.get("id"),
            "provider": provider,
            "providerName": meta.get("name", provider),
            "baseUrl": meta.get("base"),
            "keyEnv": meta.get("key"),
            "display": display_name,
            "displayName": f"{price_tag}{display_name} — {provider}",
            "id": f"custom:{price_tag}{display_name} — {provider}",
            "in": in_price,
            "out": out_price,
            "ctx": m.get("context_window") or 0,
            "maxout": m.get("max_completion_tokens") or m.get("context_window") or 0,
            "tools": m.get("tools_supported") or False,
            "img": m.get("vision") or False,
            "vendor": m.get("vendor"),
            "tier": m.get("tier"),
            "freeKind": "free" if (in_price == 0 and out_price == 0) else ("tier" if m.get("free_kind") == "tier" else "cost"),
        }
        models.append(model_dict)
    
    if skipped > 0:
        print(f"Skipped {skipped} models from providers without keys.")
    
    # Sync to local apps
    print(f"\n=== syncing {len(models)} models to local apps ===")
    args.apps = None
    args.yes = True
    args.profile = "all-free"  # Set default profile
    rc = cmd_apply(args, models, keys)
    if rc != 0:
        print("Local sync failed.")
        return rc
    
    # Sync to Hetzner Droid
    print("\n=== syncing to Hetzner Droid ===")
    rc = engine.apply(models, True)
    if rc != 0:
        print("Hetzner sync failed.")
        return rc
    
    print("\n=== Sync complete! ===")
    return 0


def _run_action(key: str, args, keys: dict) -> int:
    if key == "live_update":
        return cmd_live(argparse.Namespace(apps=None, yes=True), keys)
    if key == "live_plan":
        return cmd_live(argparse.Namespace(apps=None, yes=False), keys)
    catalog = load_catalog()
    if key == "local_update":
        return cmd_sync(argparse.Namespace(profile=args.profile, apps=None, yes=True), keys)
    if key == "local_plan":
        return cmd_plan(argparse.Namespace(profile=args.profile, apps=None),
                        build_models(args.profile, catalog), keys)
    if key == "local_status":
        return cmd_status(argparse.Namespace(profile=args.profile, apps=None),
                          build_models(args.profile, catalog), keys)
    if key == "doctor":
        return cmd_doctor(argparse.Namespace(profile=args.profile),
                          build_models(args.profile, catalog), keys)
    if key == "engine_update":
        print("refreshing provider catalogs first...\n")
        rc = cmd_refresh(argparse.Namespace(profile=args.profile), [], keys)
        if rc != 0:
            print("refresh failed; using the last good catalog")
        return engine.apply(build_models("under40", load_catalog()), True)
    if key == "engine_plan":
        return engine.plan(build_models("under40", catalog))
    if key == "engine_status":
        return engine.status()
    if key == "engine_rollback":
        return engine.rollback()
    return 1


def _launcher(args, keys: dict) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("modelhub launcher needs an interactive terminal.")
        print("Use: modelhub live --yes | modelhub sync | modelhub plan | modelhub engine apply --yes")
        return 1
    while True:
        idx = launcher.select()
        if idx is None:
            return 0
        item = launcher.ITEMS[idx]
        if item["key"] == "quit":
            return 0
        print("\n" + "=" * 66)
        print("  " + item["title"])
        print("=" * 66 + "\n")
        try:
            rc = _run_action(item["key"], args, keys)
        except KeyboardInterrupt:
            print("\ninterrupted")
            rc = 130
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            rc = 1
        print(f"\n[{'ok' if rc == 0 else 'exit ' + str(rc)}]")
        try:
            input("\nPress Enter to return to modelhub...")
        except (EOFError, KeyboardInterrupt):
            return rc


def main():
    from lib.banner import print_banner
    print_banner()
    ap = argparse.ArgumentParser(
        prog="modelhub",
        description="No subcommand: open the interactive control deck.",
        epilog="Examples: modelhub | modelhub plan | modelhub apply --apps droid --yes",
    )
    ap.add_argument("--profile", default="all-free", choices=sorted(PROFILES))
    sub = ap.add_subparsers(dest="cmd", required=False)

    p = sub.add_parser("live", help="catalog live: update apps from the engine's /v1/vibe (plan unless --yes)")
    p.add_argument("--apps"); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("sync", help="direct from provider: refresh provider catalogs, then update apps"); p.add_argument("--apps"); p.add_argument("--skip-refresh", action="store_true")
    p = sub.add_parser("plan"); p.add_argument("--apps")
    p = sub.add_parser("apply"); p.add_argument("--apps"); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--apps")
    p = sub.add_parser("list")
    sub.add_parser("doctor")
    sub.add_parser("refresh")
    p = sub.add_parser("save-list"); p.add_argument("file")
    p = sub.add_parser("run"); p.add_argument("app", choices=sorted(BINARIES)); p.add_argument("rest", nargs=argparse.REMAINDER)
    p = sub.add_parser("rollback"); p.add_argument("--app", required=True, choices=sorted(APP_FILES)); p.add_argument("--to", required=True)
    sub.add_parser("sync-from-engine")
    p = sub.add_parser("engine")
    esp = p.add_subparsers(dest="engine_cmd", required=True)
    esp.add_parser("plan")
    a = esp.add_parser("apply"); a.add_argument("--yes", action="store_true")
    esp.add_parser("status")
    r = esp.add_parser("rollback"); r.add_argument("--to")

    args = ap.parse_args()
    keys = load_keys()

    if args.cmd is None:
        return _launcher(args, keys)
    if args.cmd == "live":
        return cmd_live(args, keys)
    if args.cmd == "sync":
        return cmd_sync(args, keys)
    if args.cmd == "sync-from-engine":
        return cmd_sync_from_engine(args, keys)

    catalog = load_catalog()
    models = build_models(args.profile, catalog)

    if args.cmd == "engine":
        engine_models = build_models("under40", catalog)
        if args.engine_cmd == "plan":
            return engine.plan(engine_models)
        if args.engine_cmd == "apply":
            return engine.apply(engine_models, args.yes)
        if args.engine_cmd == "status":
            return engine.status()
        if args.engine_cmd == "rollback":
            return engine.rollback(args.to)
        return 1

    if args.cmd == "refresh":
        return cmd_refresh(args, models, keys)
    if args.cmd == "plan":
        return cmd_plan(args, models, keys)
    if args.cmd == "apply":
        return cmd_apply(args, models, keys)
    if args.cmd == "status":
        return cmd_status(args, models, keys)
    if args.cmd == "list":
        return cmd_list(args, models, keys)
    if args.cmd == "save-list":
        from lib.banner import save_list
        print(f"saved -> {save_list(models, args.file)}")
        return 0
    if args.cmd == "doctor":
        return cmd_doctor(args, models, keys)
    if args.cmd == "run":
        return cmd_run(args, models, keys)
    if args.cmd == "rollback":
        return cmd_rollback(args, models, keys)
    return 0


if __name__ == "__main__":
    sys.exit(main())
