"""ASCII banners for modelhub / modelhub-vibe. Picks one at random per run."""
from __future__ import annotations

import random
from pathlib import Path

from .catalog import PROVIDERS

BANNERS = [
    # 1: block letters "MODELHUB"
    r"""
                   ▀▀     ▀▀ ▀▀▀▀▀▀ ▀▀▀▀▀▀  ▀▀▀▀▀▀▀
                    ▀▀   ▀▀    ▀▀   ▀▀   ▀▀ ▀▀
                     ▀▀ ▀▀     ▀▀   ▀▀▀▀▀▀  ▀▀▀▀▀
                      ▀▀▀      ▀▀   ▀▀   ▀▀ ▀▀
                       ▀     ▀▀▀▀▀▀ ▀▀▀▀▀▀  ▀▀▀▀▀▀▀
▀▀▀▀▀▀▀ ▀▀▀▀▀▀  ▀▀▀▀▀▀▀  ▀▀▀▀▀  ▀▀   ▀▀       ▀▀▀   ▀▀ ▀▀▀▀▀▀▀ ▀▀▀▀▀▀
▀▀      ▀▀   ▀▀ ▀▀      ▀▀      ▀▀   ▀▀       ▀▀▀▀  ▀▀ ▀▀      ▀▀   ▀▀
▀▀▀▀▀   ▀▀▀▀▀▀  ▀▀▀▀▀    ▀▀▀▀▀  ▀▀▀▀▀▀▀ ▀▀▀▀▀ ▀▀ ▀▀ ▀▀ ▀▀▀▀▀   ▀▀▀▀▀▀
▀▀      ▀▀  ▀▀  ▀▀           ▀▀ ▀▀   ▀▀       ▀▀  ▀▀▀▀ ▀▀      ▀▀  ▀▀
▀▀      ▀▀   ▀▀ ▀▀▀▀▀▀▀ ▀▀▀▀▀▀  ▀▀   ▀▀       ▀▀   ▀▀▀ ▀▀▀▀▀▀▀ ▀▀   ▀▀
""",
    # 2: shaded "MODEL HUB"
    r"""
                  ▀██▀  ▓▀██▀ ▀▀█▀ ▀██▀▀▀█▄ ▀██▀▀▀█▄
                  ▀▀▄█   ▒█▀  ▓██  ▓██ ▄▄█▀ ▓██  ▀▀▀
                   ░▀█▌ ░▐█   ▒██  ▒█▄▀▀█▄  ▒█▄▀▀
                    ░▀█▌▐█▀   ░██  ░██ ▀▀██ ░██
                     ░▀██▀    ▄██▄ ▄██▄▄▄█▀ ▄██▄▄▄█▀
                       ▀▀     ▀▀▀▀ ▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀
""",
    # 3: double-line "MODELHUB" wide
    r"""
▀██▀▀▀█▄ ▀██▀▀██▄   ▀██▀▀▀█▄ ▄▄▄▀▀█▄ ▀██▀▒▀██▀  ▄    ▓▀█▀ ▀██▀▀▀█▄ ▀██▀▀██▄
▓██  ▀▀▀ ▓██ ▒▐█▀   ▓██  ▀▀▀ ██▀ ▀▀▀ ▓██  ▓██  ░▄█▄   ▒█  ▓██  ▀▀▀ ▓██ ▒▐█▀
▒█▄▀▀    ▒██▄▄█▀    ▒█▄▀▀    ▀▀█▄▄▄  ▒█▄▀▀▀██  ▒█▀▀█▄ ░█  ▒█▄▀▀    ▒██▄▄█▀
░██      ░██▀▀▄█▄   ░██       ▀▀▀▀▄█ ░██  ▒██  ░█ ▀▀▀█▄█  ░██      ░██▀▀▄█▄
▄██▄     ▄██▄▀▀▀██▄ ▄██▄▄▄█▀ ██▄▄▄█▀ ▄██▄▄▄██▄ ▄█▄  ▀▀▀█  ▄██▄▄▄█▀ ▄██▄▀▀▀██▄
▀▀▀▀     ▀▀▀▀  ▀▀▀▀ ▀▀▀▀▀▀▀  ▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀ ▀▀▀    ▀▀  ▀▀▀▀▀▀▀  ▀▀▀▀  ▀▀▀▀
""",
    # 4: banner letters
    r"""
                     ▓▒▄   ▓▒▄  ▓▒▄  ▓▒░   ▄  ▓▒░    ▄
                     ▒░█   ▒░█   ▀▀  ▒░█▀▀  ▄ ▒░█▀▀▀▀▀
                     ░ █   ░ █ ▓▒░ ▄ ░     █▀ ░    ▄
                        ▄   █▀  ░ █▀   █▀▀  ▄   █▀▀▀
                           █▀  ▓▒░ ▄       █▀        ▄
                        ▀▀▀▀    ▀▀▀▀  ▀▀▀▀▀▀   ▀▀▀▀▀▀▀
""",
    # 5: box-drawing "MODELHUB"
    r"""
                       ┌──┐   ┌──┐┌──┐┌────────┐ ┌────────┐
                       │  │   │·.││  ││ ·┌───┐·└┐│· ┌─────┘
                       │· │   │  ││· ││. │┌──┘ ┌┘│  └──┐
                       └┐─└┐ ┌┘─┌┘│──││──│└──┐──││──┌──┘
                        └┐═└─┘═┌┘ │══││══└───┘═┌┘│══└─────┐
                         └─────┘  └──┘└────────┘ └────────┘
""",
]

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLORS = ["\033[36m", "\033[35m", "\033[33m", "\033[32m", "\033[34m", "\033[91m", "\033[95m", "\033[96m"]


def banner(color: bool = True, rng: random.Random | None = None) -> str:
    art = (rng or random).choice(BANNERS)
    if color:
        c = random.choice(COLORS)
        return c + BOLD + art + RESET
    return art


def _supports_color() -> bool:
    import os, sys
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def print_banner() -> None:
    print(banner(color=_supports_color()))


def report(apps_stats: list[tuple[str, int]], models: list[dict], out=print) -> None:
    """Color-coded listing of apps updated (with model counts), then
    providers with per-provider model counts."""
    use = _supports_color()
    c = (lambda s, col: f"{col}{BOLD}{s}{RESET}" if use else (lambda s: s))(0, "")  # placeholder

    def paint(s: str, col: str) -> str:
        return f"{col}{s}{RESET}" if use else s

    out(paint("\nAPPS UPDATED", "\033[36m"))
    out(paint("─" * 44, "\033[36m"))
    total = 0
    for i, (label, n) in enumerate(apps_stats):
        total += n
        col = COLORS[i % len(COLORS)]
        out(f"  {paint(f'{label:<22}', col)} {paint(f'{n:>5} models', col)}")
    out(f"  {paint('TOTAL', BOLD)} {paint(f'{total} models', BOLD)}")

    out(paint("\nPROVIDERS", "\033[35m"))
    out(paint("─" * 44, "\033[35m"))
    counts: dict[str, int] = {}
    for m in models:
        counts[m["provider"]] = counts.get(m["provider"], 0) + 1
    for i, (gw, n) in enumerate(sorted(counts.items(), key=lambda kv: -kv[1])):
        col = COLORS[i % len(COLORS)]
        out(f"  {paint(f'⦗{gw.upper()}⦘', col)} {paint(f'{n:>5} models', col)}")
    out(f"  {paint('TOTAL', BOLD)} {paint(f'{len(models)} models / {len(counts)} providers', BOLD)}")


def save_list(models: list[dict], path: str) -> str:
    """Write all models grouped by provider with prices to a txt file."""
    lines = ["modelhub model list", "=" * 60, ""]
    counts: dict[str, list[dict]] = {}
    for m in models:
        counts.setdefault(m["provider"], []).append(m)
    for gw in sorted(counts):
        lines.append(f"⦗{gw.upper()}⦘  ({len(counts[gw])} models)  {PROVIDERS.get(gw, {}).get('base', '')}")
        lines.append("-" * 60)
        for m in sorted(counts[gw], key=lambda x: x["display"].lower()):
            inp, outp = m.get("in") or 0, m.get("out") or 0
            price = "FREE" if (inp == 0 and outp == 0) else f"${inp:.2f} in / ${outp:.2f} out per 1M"
            lines.append(f"  {m['display']}")
            lines.append(f"      id: {m['apiId']}   price: {price}   ctx: {m.get('ctx') or '-'}")
        lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
