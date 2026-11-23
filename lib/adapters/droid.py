"""Droid / Factory adapter."""
from __future__ import annotations

import json
from pathlib import Path

from ..catalog import PROVIDERS
from ..safety import dumps_json
from .base import FileWrite, Plan, default_model, key_for

PATH = Path.home() / ".factory" / "settings.json"
MANAGED = ("[FREE]", "[FREE TIER]", "[COST ")
LEGACY_PROVIDER = "generic-chat-completion-api"
_GATEWAY_HEADS = {p.upper() for p in PROVIDERS}


def _is_managed(display: str) -> bool:
    """An entry we generated: new ⦗GATEWAY⦘… style, old [FREE]/[COST] tags,
    or the previous plain GATEWAY: model-id style."""
    if not display:
        return False
    if display.startswith("⦗") or display.startswith(MANAGED):
        return True
    head = display.split(":", 1)[0]
    return ":" in display and head in _GATEWAY_HEADS


def _same_model_name(old_display: str, new_display: str) -> bool:
    """True when an old-style display and a new-style display name the same
    model (ignoring ⦗G⦘SYM wrappers, ░ markers, price tags, and old
    [FREE]/[COST]/GATEWAY: prefixes)."""
    import re
    def core(s: str) -> str:
        s = re.sub(r"⦗[^⦘]*⦘.?", "", s)          # ⦗GATEWAY⦘SYM
        s = re.sub(r"^[A-Z0-9-]+:", "", s)          # GATEWAY:
        s = re.sub(r"^\[(FREE|FREE TIER|CLOUD|COST)[^\]]*\]\s*", "", s)  # [TAG]
        s = s.replace("░", " ").strip()
        s = re.sub(r"⟦.*$", "", s).strip()          # ⟦price⟧
        # drop marketing words; compare on the model-ish tokens
        tokens = [t for t in re.split(r"[\s\-—/]+", s.lower())
                  if t and t not in {"inference", "the", "a", "and", "free", "tier", "cloud"}]
        return " ".join(tokens)
    a, b = core(old_display), core(new_display)
    return bool(a) and (a == b or a in b or b in a)


def build(models: list[dict], keys: dict) -> Plan:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    existing = data.get("customModels") or []

    # Anything currently referenced as active is untouchable. Losing one of
    # these is what killed the running session, so protect them by id.
    protected: set[str] = set()
    # Also protect by (baseUrl, model): if the referenced entry's id is an
    # old-naming id of a model we are about to generate, that entry is the
    # same model and must be kept (not dropped as a dupe).
    protected_api: set[tuple] = set()
    existing_by_id = {m.get("id"): m for m in existing if m.get("id")}

    def protect(container, key: str) -> None:
        if isinstance(container, dict):
            value = container.get(key)
            if isinstance(value, str) and value.startswith("custom:"):
                protected.add(value)
                m = existing_by_id.get(value)
                if m:
                    protected_api.add((m.get("baseUrl"), m.get("model")))

    protect(data.get("sessionDefaultSettings"), "model")
    protect(data.get("sessionDefaultSettings"), "specModeModel")
    protect(data, "specModeModel")
    protect(data.get("subagentModelSettings"), "lightModel")
    protect(data.get("subagentModelSettings"), "mediumModel")
    protect(data.get("subagentModelSettings"), "heavyModel")
    protect(data.get("missionModelSettings"), "workerModel")
    protect(data.get("missionModelSettings"), "validationWorkerModel")
    protect(data, "imageGenerationModel")

    manual = []
    rebuilt = 0
    covered: set[tuple] = set()  # (baseUrl, apiId) already present via a kept entry
    old_ids = {m.get("id") for m in existing if m.get("id")}
    gen_by_api = {(n.get("baseUrl"), n.get("apiId")): n for n in models}
    for m in existing:
        dn = m.get("displayName") or ""
        is_old_managed = (dn.startswith("⦗") or dn.startswith(MANAGED)
                          or dn.startswith("[CLOUD]") or _is_managed(dn))
        key = (m.get("baseUrl"), m.get("model"))
        if key in gen_by_api:
            g = gen_by_api[key]
            if m.get("id") in protected or key in protected_api:
                # Active/referenced entry: NEVER change its id (that killed a
                # running session before). Keep the id, refresh the cosmetic
                # fields to the current naming, and don't emit a generated
                # dupe for it.
                covered.add(key)
                m = dict(m)
                m["model"] = g["apiId"]
                m["baseUrl"] = g["baseUrl"]
                m["displayName"] = g["display"]
                if g.get("maxout"):
                    m["maxOutputTokens"] = int(g["maxout"])
                manual.append(m)
                continue
            # Any other existing entry on this exact endpoint+model is a dupe
            # of the generated one: drop it, the rebuild replaces it.
            rebuilt += 1
            continue
        if m.get("id") in protected:
            manual.append(m)
            continue
        # Managed-style entries from earlier syncs with no generated twin.
        if is_old_managed:
            rebuilt += 1
            continue
        # Media models (image/video/TTS/OCR) are not chat routes; keep the
        # hand-written entry instead of generating a chat-shaped dupe.
        hay = f"{m.get('model') or ''} {m.get('displayName') or ''}".lower()
        if any(n in hay for n in ("image", "video", "tts", "speech", "ocr", "whisper", "transcribe", "wan", "seedance", "grok-imagine", "flux", "sdxl", "audio")):
            manual.append(m)
            continue
        # Everything else is hand-written or legacy. Keep it. Aggressive
        # cleanup is opt-in later, never automatic.
        manual.append(m)

    warnings: list[str] = []
    missing: set[str] = set()
    new = []
    for m in models:
        # A kept entry already covers this endpoint+model (e.g. a protected
        # active model kept under its old id): don't emit a dupe.
        if (m["baseUrl"], m["apiId"]) in covered:
            continue
        api_key = key_for(keys, m)
        if not api_key:
            missing.add(m["keyEnv"])
            continue
        # Media-only models (image/video/TTS/OCR) don't belong in a chat
        # picker; the hand-written entry for them is kept instead.
        hay = f"{m['apiId']} {m['display']}".lower()
        if any(n in hay for n in ("image", "video", "tts", "speech", "ocr", "whisper", "transcribe", "wan", "seedance", "grok-imagine", "flux", "sdxl", "audio")):
            continue
        obj = {
            "model": m["apiId"],
            "id": "custom:" + m["display"],
            "baseUrl": m["baseUrl"],
            "apiKey": api_key,
            "provider": LEGACY_PROVIDER,
            "displayName": m["display"],
        }
        if m.get("maxout"):
            obj["maxOutputTokens"] = int(m["maxout"])
        if m.get("img") is False:
            obj["noImageSupport"] = True
        new.append(obj)

    if missing:
        warnings.append("missing keys, skipped: " + ", ".join(sorted(missing)))

    new_ids = {m.get("id") for m in new}
    # Drop a manual entry only when it is a true dupe of a generated entry
    # (same id, or same endpoint+model) AND it is not the protected/referenced
    # one. Everything else hand-written stays.
    def keep_manual(m):
        # The referenced (protected) entry is untouchable, by id.
        if m.get("id") in protected:
            return True
        # Anything else on an endpoint+model we generate is a dupe: drop it.
        if m.get("id") in new_ids:
            return False
        if (m.get("baseUrl"), m.get("model")) in gen_by_api:
            return False
        return True
    manual = [m for m in manual if keep_manual(m)]
    kept_refs = len(protected.intersection({m.get("id") for m in manual}))
    if kept_refs:
        warnings.append(f"kept {kept_refs} referenced legacy entr{'y' if kept_refs == 1 else 'ies'}")

    combined = new + manual
    for i, m in enumerate(combined):
        m["index"] = i
    data["customModels"] = combined

    new_ids_all = {m.get("id") for m in combined if m.get("id")}
    removed = len(old_ids - new_ids_all)

    valid = {m.get("id") for m in combined if m.get("id")}
    pref = default_model([m for m in models if key_for(keys, m)])
    fallback = "custom:" + pref["display"] if pref else None
    if fallback is None:
        fallback = next((m["id"] for m in new if m.get("id")), None)
    if fallback is None:
        fallback = next((m.get("id") for m in manual if m.get("id")), None)

    # Repoint any ref whose target id is no longer present. If the dangling
    # id matches a generated model's OLD naming, point at the NEW id instead
    # of the generic fallback so the user's selection survives the reformat.
    def fix_ref(container: dict | None, key: str, label: str) -> None:
        if not isinstance(container, dict) or not fallback:
            return
        cur = container.get(key)
        if cur and cur not in valid:
            target = fallback
            if isinstance(cur, str) and cur.startswith("custom:"):
                cur_name = cur[len("custom:"):]
                for n in new:
                    if n.get("id") and n["id"] != cur and _same_model_name(cur_name, n["display"]):
                        target = n["id"]
                        break
            container[key] = target
            warnings.append(f"{label}: {cur} -> {target}")

    fix_ref(data.get("sessionDefaultSettings"), "model", "sessionDefaultSettings.model")
    fix_ref(data.get("sessionDefaultSettings"), "specModeModel", "sessionDefaultSettings.specModeModel")
    fix_ref(data, "specModeModel", "specModeModel")
    fix_ref(data.get("subagentModelSettings"), "lightModel", "subagent.light")
    fix_ref(data.get("subagentModelSettings"), "mediumModel", "subagent.medium")
    fix_ref(data.get("subagentModelSettings"), "heavyModel", "subagent.heavy")
    fix_ref(data.get("missionModelSettings"), "workerModel", "mission.worker")
    fix_ref(data.get("missionModelSettings"), "validationWorkerModel", "mission.validation")

    if pref and pref.get("provider") == "hetzner":
        target = "custom:" + pref["display"]
        if target in valid:
            ss = data.setdefault("sessionDefaultSettings", {})
            ss["model"] = target
            ss["specModeModel"] = target
            data["specModeModel"] = target
            for key in ("lightModel", "mediumModel", "heavyModel"):
                if isinstance(data.get("subagentModelSettings"), dict):
                    data["subagentModelSettings"][key] = target
            for key in ("workerModel", "validationWorkerModel"):
                if isinstance(data.get("missionModelSettings"), dict):
                    data["missionModelSettings"][key] = target
            data["modelFavorites"] = list(dict.fromkeys(
                [target] + [f for f in (data.get("modelFavorites") or []) if f != target]
            ))[:12]
            warnings.append(f"default set to {target}")

    favs = [f for f in (data.get("modelFavorites") or []) if f in valid]
    if not favs:
        favs = [m["id"] for m in new[:8] if m.get("id")]
    data["modelFavorites"] = list(dict.fromkeys(favs))

    return Plan(
        app="droid",
        label="Droid / Factory",
        files=[FileWrite(PATH, dumps_json(data), "json", 0o600)],
        stats={"managed": len(new), "removed": removed, "rebuilt": rebuilt, "manual": len(manual), "kept_refs": kept_refs},
        warnings=warnings,
        note="active model, spec model, subagents and favorites re-pointed when dangling",
    )
