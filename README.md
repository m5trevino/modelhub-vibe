# modelhub-vibe installer bundle

This is the bundle the catalog site's **INSTALL TO CLI APPS** button packages into
`/root/modelhub-installers/modelhub-install.sh` on the Hetzner engine.

- `vibe_sync.py` — fetches the live `/v1/models` catalog, merges provider-direct
  model lists, and applies them to every CLI coding app found on the machine.
- `modelhub.py` + `lib/` — the modelhub package (adapters, banner, safety).
- `build_installer.py` — packs this directory into the one-file installer.

Install command (from https://catalog.save-aichats.com):
    ssh engine 'cat /root/modelhub-installers/modelhub-install.sh' | bash
Preview (writes nothing):
    ssh engine 'cat /root/modelhub-installers/modelhub-install.sh' | bash -s -- --plan

Secrets are never committed: provider keys live only in the root-only installer
file on the engine, generated at install time from the engine's own key pools.
