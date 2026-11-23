from pathlib import Path
p = Path("/root/hetzner/ai-engine/app/core/config_store.py")
s = p.read_text()
if "# MODELHUB ALLOWED PROVIDERS" in s:
    print("store already patched")
    raise SystemExit(0)
anchor = 'CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "runtime_config.json"\n'
if anchor not in s:
    print("store anchor missing")
    raise SystemExit(2)
insert = r"""

# MODELHUB ALLOWED PROVIDERS
def _modelhub_allowed_providers():
    try:
        _hub = json.loads((Path(__file__).resolve().parent.parent.parent / "modelhub_models.json").read_text())
        return set(_hub.get("keep_gateways") or []) | {m.get("gateway") for m in (_hub.get("models") or []) if m.get("gateway")}
    except Exception:
        return {"groq", "hetzner", "openrouter", "novita", "xkiro", "merge", "ollama"}

ALLOWED_PROVIDERS = _modelhub_allowed_providers()
"""
s = s.replace(anchor, anchor + insert, 1)
old_prop = '''    @property
    def providers(self) -> Dict[str, Any]:
        """Return the provider state map (enabled + visible flags)."""
        return self._data.get("providers", DEFAULT_CONFIG["providers"]).copy()
'''
new_prop = '''    @property
    def providers(self) -> Dict[str, Any]:
        """Return the provider state map, filtered to modelhub gateways."""
        data = self._data.get("providers", DEFAULT_CONFIG["providers"])
        return {k: v for k, v in data.items() if k in ALLOWED_PROVIDERS}
'''
if old_prop not in s:
    print("property anchor missing")
    raise SystemExit(3)
s = s.replace(old_prop, new_prop, 1)
old_en = '''    def is_provider_enabled(self, gateway: str) -> bool:
        """Check if a provider is enabled for use."""
        cfg = self._data.get("providers", DEFAULT_CONFIG["providers"]).get(gateway, {})
        return bool(cfg.get("enabled", False)) and bool(cfg.get("visible", False))
'''
new_en = '''    def is_provider_enabled(self, gateway: str) -> bool:
        """Check if a provider is enabled for use."""
        if gateway not in ALLOWED_PROVIDERS:
            return False
        cfg = self._data.get("providers", DEFAULT_CONFIG["providers"]).get(gateway, {})
        return bool(cfg.get("enabled", False)) and bool(cfg.get("visible", False))
'''
if old_en not in s:
    print("enabled anchor missing")
    raise SystemExit(4)
s = s.replace(old_en, new_en, 1)
old_vis = '''    def is_provider_visible(self, gateway: str) -> bool:
        """Check if a provider should be shown in the UI."""
        cfg = self._data.get("providers", DEFAULT_CONFIG["providers"]).get(gateway, {})
        return bool(cfg.get("visible", False))
'''
new_vis = '''    def is_provider_visible(self, gateway: str) -> bool:
        """Check if a provider should be shown in the UI."""
        if gateway not in ALLOWED_PROVIDERS:
            return False
        cfg = self._data.get("providers", DEFAULT_CONFIG["providers"]).get(gateway, {})
        return bool(cfg.get("visible", False))
'''
if old_vis not in s:
    print("visible anchor missing")
    raise SystemExit(5)
s = s.replace(old_vis, new_vis, 1)
tmp = p.with_suffix(".py.tmp")
tmp.write_text(s)
tmp.replace(p)
print("store patched")
