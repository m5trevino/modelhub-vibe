"""Curses launcher for modelhub."""
from __future__ import annotations

import curses
import locale
import sys

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass


ART = r"""
                          ▄▄▄▄▄▄                 ▄▄▄▄▄▄▄▄                                         ▄▄                  
               ▄▄▄▄▄▄▄██████▄▓████▄▄▄          ▄▄██▓▀▀▀██▓▄▄     ▄▄     ▄▄▄   ▄▄▄▄▄▓ ▄▄▄▄▄     ▄▄▄▀▓▌    ▄▄▓████▄▄▄   
          ▄▄▄█████▓█████▀ █████▀▀██▓█▄▄      ▄▄███▄████▓▄██▀   ▄▄█▌     ▐███  ▐███▄█ ██████    █████▌  ▄▄████▄▓█████  
         ▄████▄██▄██      ▐▓▄▓█▄  ▀█▄▓█▌    ▐█▄█▓█▀    ▀▀█    ▒▓██▌     ▐█▄██ ▐█▓█▄█ ███▄██▄▄  ▐▓▄▓█▌ ▒▓██▓▀    ▀█▄██ 
              ▐███▓█       ▐████  ▄████▌     ▐███████▒▌      ░▓███▌      ▐██▓▌▐▓███▌ ▐██████▓▓▄▐█▓███░▓███▌      ▐██▓▌
               ▐███▌       ▐▓███████▀▀▄     ▐█████▌          ▐████▌     ▄▐███▌▐████▌▌▐█████████▓████▒▐████▌      ▐███▌
               ▐████▌      ▐█████▀▀████▄     ▐█▄▄██▄▄         ▐███▓▄▄  ▄▓▓██▓▀ ▐███▌ ▐████▌▀▀███████░ ▐███▓▄    ▐▓██▌ 
               ▐▓████       █████▌ ▀█████▄    ▀▐█████▓████▓░█  ▀████▓██████▀   █████ ▐████▌  ▀█▓▓████ ▀█████▓███████  
                ▓███▀▌      ▀▓██▀    ▀▀████▄     ▀▀▀▀██████▓     ▀▀▀████▀▀     ▐▀███ ▐███▓▌    ▀███▀▓   ▀▀▀▀████▀▀    
                ▀▀          ▀                                                                                         

                                          ▄                ▄▄▄▄▄▄▄▄     █▄▄                          ▄▄                  ▄▄▄▄▄▄         
    ▄▄▓█▄▄▄▄▄███▄▄▄       ▄▄▓████▄▄▄   ▄▄▄██▄▄           ▄▄██▓▀▀▀██▓▄▄ ▐███▄▄           ▄▄▄▄▄     ▄▄▄▀▓▌    ▄▄     ▄▄▄   ██▄▓████▄▄▄    
  ▄▄████████████████    ▄▄████▄▓█████  ███▒▄▓██▄▄      ▄▄███▄████▓▄██▀ ▐█▄███           ██████   ▐█████▌  ▄▄█▌     ▐███  █████▀▀██▓█▄▄  
 ▒▓██▓▀▀▀█▄███▀ ▀█▄██  ▒▓██▓▀    ▀█▄██ █▓█▄█▀███▓▓▄▄  ▐█▄█▓█▀    ▀▀█   ▐█▄█▓█▌          ███▄██▌   ▐▓▄▓█▌ ▒▓██▌     ▐█▄██ ▐▓▄▓█▄  ▀█▄▓█▌ 
░▓███▌   ▐██▓▌   ▐██▓▌░▓███▌      ▐██▓▌▐████   ▀▒▒▒▒▓  ▐███████▒▌      ▐▐███▓▌          ▐█████▌   ▐█▓███░▓███▌      ▐██▓▌ ▐████  ▄██▀▀  
▐████▌   ▐███▌   ▐███▌▐████▌      ▐███▌▐████▌    ▐▓▓█▓▐█████▌          ▐█████▌          ▐█████████▓████▒▐████▌      ▐███▌ ▐▓████▀▀▀██▄  
 ▐███▓   ▓███▌   ▓██▒▌ ▐███▓▄    ▐▓██▌  ▐███▌    ▐███▌ ▐█▄▄██▄▄         ▐█▄▄██▄▄        ▐█████▀▀▀▀▀████░ ▐███▓▄    ▄▓██▌  ▐███▌    ▐███▌
 ▀████▌  ▐██▌    ▐██▓▀ ▀█████▓███████   ▐███▄▄▄▄▄███▌   ▀▐█████▓████▓░█  ▀▐█████▓████▓░█▐████▌    ▐▓████ ▀█████▓███████   ▐███▄▄▄▄▄███▌ 
   ▀▀▀    ▀▀▀     ▀▀▀    ▀▀▀▀████▀▀     ▐▓███████▀▀▀       ▀▀▀▀██████▓      ▀▀▀▀██████▓ ▐███▓▌     ███▀▓   ▀▀▀▀████▀▀     ▐▓███████▀▀▀  
                                           ▀▀▀▀                                                                              ▀▀▀▀
"""

COMPACT = r"""
  ███╗   ███╗ ██████╗ ██████╗ ███████╗██╗     ██╗  ██╗██╗   ██╗██████╗
  ████╗ ████║██╔═══██╗██╔══██╗██╔════╝██║     ██║  ██║██║   ██║██╔══██╗
  ██╔████╔██║██║   ██║██║  ██║█████╗  ██║     ███████║██║   ██║██████╔╝
  ██║╚██╔╝██║██║   ██║██║  ██║██╔══╝  ██║     ██╔══██║██║   ██║██╔══██╗
  ██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗███████╗██║  ██║╚██████╔╝██████╔╝
  ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝
"""

ITEMS = [
    {"key": "live_update",   "title": "[CATALOG LIVE] Update coding apps",   "desc": "NEW: engine /v1/vibe, usable models, each app on its real provider gateway"},
    {"key": "live_plan",     "title": "[CATALOG LIVE] Preview changes",      "desc": "NEW: read-only diff from the live catalog"},
    {"key": "local_update",  "title": "[DIRECT FROM PROVIDER] Update coding apps", "desc": "OLD: refresh each provider's catalog and write all 8 local apps"},
    {"key": "local_plan",    "title": "[DIRECT FROM PROVIDER] Preview changes",    "desc": "OLD: read-only diff for the local apps"},
    {"key": "local_status",  "title": "Local status",               "desc": "In-sync / pending for each app"},
    {"key": "engine_update", "title": "Update Hetzner engine",      "desc": "Refresh, write 256 models, restart peacock-engine"},
    {"key": "engine_plan",   "title": "Preview engine changes",      "desc": "Read-only diff for the Hetzner engine"},
    {"key": "engine_status", "title": "Engine status",               "desc": "Health, model count, registry by gateway"},
    {"key": "engine_rollback", "title": "Rollback engine",           "desc": "Restore the latest server backup and restart"},
    {"key": "doctor",        "title": "Run doctor",                  "desc": "Configs, keys, duplicates, dangling refs"},
    {"key": "quit",          "title": "Quit",                        "desc": "Exit modelhub"},
]


def _clean(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _groups(lines: list[str]) -> list[list[str]]:
    groups, cur = [], []
    for line in lines:
        if line.strip():
            cur.append(line)
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _width(group: list[str]) -> int:
    return max((len(x) for x in group), default=0)


def _init_colors() -> tuple[list[int], int]:
    if not curses.has_colors():
        return [], 0
    try:
        curses.start_color()
    except curses.error:
        return [], 0
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = 0
    if curses.COLORS >= 256:
        codes = [93, 99, 105, 171, 177, 183, 189, 195, 46, 82, 118, 154]
    else:
        codes = [curses.COLOR_MAGENTA, curses.COLOR_GREEN]
    pairs = []
    for i, code in enumerate(codes):
        try:
            curses.init_pair(i + 1, code, bg)
            pairs.append(i + 1)
        except curses.error:
            pass
    sel = 0
    try:
        if curses.COLORS >= 256:
            curses.init_pair(90, curses.COLOR_BLACK, 93)
        else:
            curses.init_pair(90, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        sel = 90
    except curses.error:
        pass
    return pairs, sel


def _safe(win, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        win.addstr(y, max(0, x), text, attr)
    except curses.error:
        pass


def _draw_group(win, group: list[str], start_y: int, term_w: int, pairs: list[int]) -> int:
    gw = _width(group)
    offset = max(0, (term_w - gw) // 2)
    for i, line in enumerate(group):
        attr = 0
        if pairs:
            idx = int(i / max(1, len(group) - 1) * (len(pairs) - 1))
            attr = curses.color_pair(pairs[idx]) | curses.A_BOLD
        _safe(win, start_y + i, offset, line, attr)
    return start_y + len(group)


def _menu(stdscr, items):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.nodelay(False)
    pairs, sel_pair = _init_colors()

    art_groups = _groups(_clean(ART))
    compact = _clean(COMPACT)
    selected = 0
    needed = len(items) + 7

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Choose the largest banner that still leaves room for the menu.
        groups = []
        if art_groups:
            full_h = sum(len(g) for g in art_groups) + len(art_groups)
            block1_h = len(art_groups[0])
            if h >= full_h + needed and w >= max((_width(g) for g in art_groups), default=0) + 2:
                groups = art_groups
            elif h >= block1_h + needed and w >= _width(art_groups[0]) + 2:
                groups = [art_groups[0]]
            elif h >= len(compact) + needed and w >= _width(compact) + 2:
                groups = [compact]
        elif h >= len(compact) + needed and w >= _width(compact) + 2:
            groups = [compact]

        y = 1
        for group in groups:
            y = _draw_group(stdscr, group, y, w, pairs) + 1

        title = "MODELHUB  //  CONTROL DECK"
        if y < h - 10:
            tattr = curses.A_BOLD
            if pairs:
                tattr |= curses.color_pair(pairs[-1])
            _safe(stdscr, y, max(0, (w - len(title)) // 2), title, tattr)
            sub = "local coding apps  +  hetzner engine"
            _safe(stdscr, y + 1, max(0, (w - len(sub)) // 2), sub, curses.A_DIM)
            y += 3
        elif y < h - 6:
            _safe(stdscr, y, max(0, (w - len(title)) // 2), title, curses.A_BOLD)
            y += 2

        menu_w = max(len(i["title"]) for i in items) + 6
        x = max(2, (w - menu_w) // 2)
        for idx, item in enumerate(items):
            line = f"  {item['title']}"
            attr = 0
            if idx == selected:
                attr = curses.A_REVERSE | curses.A_BOLD
                if sel_pair:
                    attr = curses.color_pair(sel_pair) | curses.A_BOLD
                _safe(stdscr, y + idx, x - 1, " " * (menu_w + 1), attr)
                _safe(stdscr, y + idx, x, f"> {item['title']}", attr)
            else:
                _safe(stdscr, y + idx, x, f"  {item['title']}", attr)

        desc = items[selected]["desc"]
        if desc:
            _safe(stdscr, h - 3, max(0, (w - len(desc)) // 2), desc, curses.A_DIM)
        footer = "↑/↓ select   ENTER run   q quit"
        _safe(stdscr, h - 1, max(0, (w - len(footer)) // 2), footer, curses.A_DIM)

        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(items)
        elif ch in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(items)
        elif ch in (ord("\n"), curses.KEY_ENTER, 10, 13):
            return selected
        elif ch in (ord("q"), 27):
            return None


def select(items=ITEMS):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    return curses.wrapper(_menu, items)
