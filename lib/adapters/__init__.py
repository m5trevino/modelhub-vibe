"""Adapter registry, Tier 1 then Tier 2."""
import importlib

from . import droid, kimchi, kilo, opencode, pi, qwen

REGISTRY = {
    "droid": droid,
    "opencode": opencode,
    "kimchi": kimchi,
    "qwen": qwen,
    "pi": pi,
    "kilo": kilo,
}

# goose and hermes need ruamel.yaml. Keep the registry importable without it
# (e.g. on the Hetzner engine host, which only has pyyaml) by registering
# them only when the import succeeds.
for _name in ("goose", "hermes"):
    try:
        REGISTRY[_name] = importlib.import_module(f".{_name}", __package__)
    except ImportError:
        pass

TIER1 = ["droid", "hermes", "opencode", "kimchi", "goose"]
TIER2 = ["qwen", "pi", "kilo"]
