#!/usr/bin/env python3
"""Build modelhub-install.sh: a one-file installer for the vibe updater.

The installer embeds vibe_sync.py + modelhub's adapters (patched so nothing is
tied to /home/flintx), unpacks them to ~/.local/share/modelhub-vibe, adds a
`modelhub-vibe` command, then runs it once. Each run re-fetches the engine's
/v1/vibe, so the installed command keeps every CLI app current.

    python3 build_installer.py OUT.sh
"""
from __future__ import annotations

import base64
import io
import re
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PATCHES = {
    "modelhub.py": [
        ('ROOT = Path("/home/flintx/modelhub")', "ROOT = Path(__file__).resolve().parent"),
    ],
    "lib/safety.py": [
        ('BACKUPS = Path("/home/flintx/modelhub/backups")',
         'BACKUPS = Path(__file__).resolve().parent.parent / "backups"'),
    ],
}

SKIP = {"__pycache__"}


def files() -> list[Path]:
    out = [ROOT / "modelhub.py", ROOT / "vibe_sync.py"]
    for p in sorted((ROOT / "lib").rglob("*.py")):
        if not SKIP & set(p.parts):
            out.append(p)
    return out


def bundle(extra: dict[str, tuple[str, int]] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in files():
            rel = p.relative_to(ROOT).as_posix()
            text = p.read_text()
            for old, new in PATCHES.get(rel, []):
                if old not in text:
                    raise SystemExit(f"patch target missing in {rel}: {old}")
                text = text.replace(old, new)
            data = text.encode()
            info = tarfile.TarInfo(rel)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
        for name, (text, mode) in (extra or {}).items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


HEADER = r"""#!/usr/bin/env bash
# modelhub-install.sh  (generated; do not edit)
# Installs `modelhub-vibe`, which reads https://engine.save-aichats.com/v1/vibe and
# rewrites the model lists of every CLI coding app (Droid, Hermes, OpenCode, Kimchi,
# Goose, Qwen Code, Pi, Kilo). Apps talk to each provider's own gateway, not the engine.
#
#   bash modelhub-install.sh            install, then update all apps now
#   bash modelhub-install.sh --plan     install, show what would change, write nothing
#   bash modelhub-install.sh --no-run   install only
#
# Provider keys are read from ${MODELHUB_ENV:-~/.config/modelhub/env} (NAME_API_KEY=value).
# This script contains no keys. Every app file is backed up before it is written.
set -euo pipefail

DEST="${MODELHUB_HOME:-$HOME/.local/share/modelhub-vibe}"
BIN="${MODELHUB_BIN:-$HOME/.local/bin}"
MODE="--yes"
RUN=1
for a in "$@"; do
  case "$a" in
    --plan) MODE="" ;;
    --no-run) RUN=0 ;;
    -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null || true; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v base64  >/dev/null || { echo "base64 is required" >&2; exit 1; }

mkdir -p "$DEST" "$BIN"
base64 -d <<'MODELHUB_PAYLOAD' | tar -xz -C "$DEST"
"""

FOOTER = r"""MODELHUB_PAYLOAD

cat > "$BIN/modelhub-vibe" <<WRAP
#!/usr/bin/env sh
exec python3 "$DEST/vibe_sync.py" "\$@"
WRAP
chmod +x "$BIN/modelhub-vibe"
echo "installed: $BIN/modelhub-vibe  (code in $DEST)"

ENV_FILE="${MODELHUB_ENV:-$HOME/.config/modelhub/env}"
if [ -f "$DEST/keys.env" ]; then
  mkdir -p "$(dirname "$ENV_FILE")"; touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
  added=0
  while IFS= read -r line; do
    name="${line%%=*}"
    [ -n "$name" ] || continue
    grep -q "^${name}=" "$ENV_FILE" || { printf '%s\n' "$line" >> "$ENV_FILE"; added=$((added+1)); }
  done < "$DEST/keys.env"
  rm -f "$DEST/keys.env"
  echo "keys: added $added missing provider key(s) to $ENV_FILE (existing ones kept)"
fi
if [ ! -s "$ENV_FILE" ]; then
  echo "note: no provider keys at $ENV_FILE; apps will only get providers that have a key there."
  echo "      add lines like OPENROUTER_API_KEY=... (see modelhub-vibe --help), then run: modelhub-vibe --yes"
fi
case ":$PATH:" in *":$BIN:"*) ;; *) echo "note: add $BIN to your PATH to use 'modelhub-vibe'";; esac

if [ "$RUN" = 1 ]; then
  SNAP=""
  [ -f "$DEST/snapshot.json" ] && SNAP="--snapshot $DEST/snapshot.json"
  python3 "$DEST/vibe_sync.py" $SNAP $MODE
fi
"""


def build_to(out: Path, stamp: str = "", snapshot: str = "", keys_env: str = "") -> dict:
    """Write the installer to `out` atomically.

    stamp     header comment (when/what it was generated from)
    snapshot  /v1/vibe JSON baked in; the first run applies exactly this set
    keys_env  NAME=value lines baked in; merged into the user's env file, never overwriting
    """
    extra = {}
    if snapshot:
        extra["snapshot.json"] = (snapshot, 0o644)
    if keys_env:
        extra["keys.env"] = (keys_env, 0o600)
    payload = base64.b64encode(bundle(extra)).decode()
    wrapped = "\n".join(payload[i:i + 76] for i in range(0, len(payload), 76))
    header = HEADER
    if stamp:
        header = header.replace("\n# modelhub-install.sh  (generated; do not edit)",
                                f"\n# modelhub-install.sh  (generated; do not edit)\n# {stamp}", 1)
    script = header + wrapped + "\n" + FOOTER
    assert re.search(r"^MODELHUB_PAYLOAD$", script, re.M)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(script)
    tmp.chmod(0o755)
    tmp.replace(out)
    return {"path": str(out), "bytes": out.stat().st_size, "files": len(files()) + len(extra)}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    info = build_to(Path(sys.argv[1]))
    print(f"wrote {info['path']} ({info['bytes'] // 1024} KB, {info['files']} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
