#!/usr/bin/env python3
"""Compact Claude Code status line. Configurable via config.json. ANSI-colored with trend vs previous period."""
import calendar
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cost import scan, business_days
from by_branch import aggregate as aggregate_branch, current_branch, fmt_tokens

stdin_ctx = {}
try:
    stdin_ctx = json.loads(sys.stdin.read() or "{}") or {}
except Exception:
    pass

DEFAULTS = {
    "segments": {
        "today": True, "week": True, "month": True,
        "remaining": True, "reset": True, "branch": True,
        "tpm": True, "tpm_chart": True,
    },
    "monthly_limit": 300.00,
    "plan_coefficient": 0.4419,
    "business_days": 5,
    "trend_tolerance_pct": 10.0,
    "tpm_overload_factor": 1.5,
    "branch_max_len": 22,
    "tpm_chart_width": 60,
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

cfg = dict(DEFAULTS)
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        user_cfg = json.load(f)
    for k, v in user_cfg.items():
        if k == "segments" and isinstance(v, dict):
            cfg["segments"] = {**DEFAULTS["segments"], **v}
        else:
            cfg[k] = v
except (OSError, json.JSONDecodeError):
    pass

DAYS = int(cfg["business_days"])
MONTHLY_LIMIT = float(cfg["monthly_limit"])
COEF = float(cfg["plan_coefficient"])
SEG = cfg["segments"]
TOL = float(cfg.get("trend_tolerance_pct", 10.0)) / 100.0
OVERLOAD = float(cfg.get("tpm_overload_factor", 1.5))
BRANCH_MAX = int(cfg.get("branch_max_len", 22))
MESES_PT = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
            "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
DIAS_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]


def c(code, text):
    return f"\033[{code}m{text}\033[0m"


BOLD = "1"
DIM = "2"
ITALIC = "3"
TEAL = "38;5;80"
GREEN = "38;5;114"
YELLOW = "38;5;221"
RED = "38;5;203"
PINK = "38;5;176"
ACCENT = "38;5;75"
LIGHT = "38;5;252"
GRAY = "38;5;244"
DEEP_GRAY = "38;5;239"
BG = "48;5;236"
BG_WARN = "48;5;52"


def trend(current, prev):
    """Return (arrow, color) comparing current to prev using ±TOL tolerance."""
    if prev is None or prev <= 0:
        return ("─", GRAY)
    delta = (current - prev) / prev
    if abs(delta) <= TOL:
        return ("─", GRAY)
    if current > prev:
        return ("↑", RED)
    return ("↓", GREEN)


def prev_month_range(ref):
    if ref.month == 1:
        y, m = ref.year - 1, 12
    else:
        y, m = ref.year, ref.month - 1
    start = ref.replace(year=y, month=m, day=1)
    last_day = calendar.monthrange(y, m)[1]
    end = ref.replace(year=y, month=m, day=min(ref.day, last_day))
    return start, end


today = datetime.now().date()
month_start = today.replace(day=1)
if month_start.month == 12:
    next_reset = month_start.replace(year=month_start.year + 1, month=1)
else:
    next_reset = month_start.replace(month=month_start.month + 1)

biz10 = business_days(DAYS * 2, today=today)
biz_current = biz10[-DAYS:]
biz_prev = biz10[:-DAYS]
yesterday = biz10[-2] if len(biz10) >= 2 else None

prev_month_start, prev_month_end = prev_month_range(today)

days_set = set(biz10)
cursor = month_start
while cursor <= today:
    days_set.add(cursor)
    cursor += timedelta(days=1)
cursor = prev_month_start
while cursor <= prev_month_end:
    days_set.add(cursor)
    cursor += timedelta(days=1)

scanned = scan(days_set)
daily = scanned["daily"]
minutes = scanned["minutes"]
today_cost = daily[today]["cost"] * COEF
yesterday_cost = (daily[yesterday]["cost"] * COEF) if yesterday else 0.0
week_cost = sum(daily[d]["cost"] for d in biz_current) * COEF
week_prev_cost = sum(daily[d]["cost"] for d in biz_prev) * COEF
month_cost = sum(daily[d]["cost"] for d in days_set if month_start <= d <= today) * COEF
month_prev_cost = sum(
    daily[d]["cost"] for d in days_set if prev_month_start <= d <= prev_month_end
) * COEF
remaining = max(MONTHLY_LIMIT - month_cost, 0.0)
reset_str = f"{next_reset.day} {MESES_PT[next_reset.month - 1]}"

biz_current_set = set(biz_current)
active_tokens = [
    tok for minute_dt, tok in minutes.items()
    if tok > 0 and minute_dt.date() in biz_current_set
]
avg_tpm = (sum(active_tokens) / len(active_tokens)) if active_tokens else 0.0
now = datetime.now().astimezone()
current_minute_key = now.replace(second=0, microsecond=0)
current_tpm = minutes.get(current_minute_key, 0)

branch_name = None
btokens = 0
bcost = 0.0
if SEG.get("branch"):
    ws = stdin_ctx.get("workspace") or {}
    branch_cwd = ws.get("current_dir") or stdin_ctx.get("cwd") or os.getcwd()
    branch_name = current_branch(cwd=branch_cwd)
    if branch_name:
        bcost_raw, btokens = aggregate_branch(branch_cwd, branch_name)
        bcost = bcost_raw * COEF


def metric(label, value, trend_arrow, trend_color):
    value_str = c(trend_color + ";1", f"${value:.2f}")
    arrow = c(trend_color + ";1", trend_arrow)
    return f"{c(GRAY, label)} {value_str} {arrow}"


def abbrev_branch(name, max_len):
    """Shorten branch preserving prefix (feat/, fix/...) and ticket (ABC-123) if present."""
    if not name or len(name) <= max_len:
        return name
    prefix = ""
    rest = name
    if "/" in name:
        head, tail = name.split("/", 1)
        if len(head) <= 6:
            prefix = head + "/"
            rest = tail
    m = re.match(r"([A-Z]{2,}-\d+)[-_]?(.*)", rest)
    if m:
        ticket, tail = m.group(1), m.group(2)
        budget = max_len - len(prefix) - len(ticket) - 1
        if budget >= 3 and tail:
            return f"{prefix}{ticket}-{tail[:budget - 1]}…"
        return f"{prefix}{ticket}"
    return f"{prefix}{rest[:max_len - len(prefix) - 1]}…"


sep = " "
mid = c(DEEP_GRAY, "  ·  ")
slash = c(DEEP_GRAY, "/")


def apply_bg(content, bg_code):
    """Wrap content with a background color, re-asserting BG after every reset inside."""
    reset_seq = "\033[0m"
    bg_seq = f"\033[{bg_code}m"
    inner = content.replace(reset_seq, f"{reset_seq}{bg_seq}")
    return f"{bg_seq} {inner} {reset_seq}"


def fmt_tpm(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}k"
    return f"{int(v)}"


BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
LEVELS_PER_ROW = 8


def daily_chart(daily_dict, ref_date, coef):
    """Stacked vertical bar chart of daily cost from day 1 through today.

    Each bar = 1 day rendered as 2 solid cols (doubled block char). Value = day cost in $.
    Returns (rows, peak, n_days).
    """
    n_days = ref_date.day
    cols = []
    for d in range(1, n_days + 1):
        day = ref_date.replace(day=d)
        entry = daily_dict[day] if day in daily_dict else {"cost": 0.0}
        cols.append(entry.get("cost", 0.0) * coef)
    peak = max(cols) if cols else 0.0

    total_levels = LEVELS_PER_ROW * 3
    empty_top = c(DEEP_GRAY, "   ")
    empty_mid = c(DEEP_GRAY, "   ")
    empty_bot = c(DEEP_GRAY, "___")
    rows = [[], [], []]
    day_colors = []
    for v in cols:
        if peak <= 0 or v <= 0:
            rows[0].append(empty_top)
            rows[1].append(empty_mid)
            rows[2].append(empty_bot)
            day_colors.append(None)
            continue
        ratio = v / peak
        level = min(total_levels, max(0, int(round(ratio * total_levels))))
        if ratio >= 0.67:
            col_color = RED
        elif ratio >= 0.34:
            col_color = YELLOW
        else:
            col_color = GREEN
        bot_level = min(LEVELS_PER_ROW, level)
        mid_level = min(LEVELS_PER_ROW, max(0, level - LEVELS_PER_ROW))
        top_level = min(LEVELS_PER_ROW, max(0, level - 2 * LEVELS_PER_ROW))
        if top_level > 0:
            mid_level = LEVELS_PER_ROW
            bot_level = LEVELS_PER_ROW
        elif mid_level > 0:
            bot_level = LEVELS_PER_ROW
        rows[0].append(c(col_color, BLOCKS[top_level] * 3))
        rows[1].append(c(col_color, BLOCKS[mid_level] * 3))
        rows[2].append(c(col_color, BLOCKS[bot_level] * 3))
        day_colors.append(col_color)
    return ["".join(r) for r in rows], peak, n_days, day_colors


def x_axis_days(ref_date, n_days, today_day, day_colors=None):
    """Two-line X axis: weekday (SEG/TER/...) on top, day number below. 3-char cells."""
    wd_cells = []
    day_cells = []
    for d in range(1, n_days + 1):
        wd = DIAS_PT[ref_date.replace(day=d).weekday()]
        day_cell = f" {d:02d}"
        bar_color = day_colors[d - 1] if day_colors else None
        if d == today_day:
            color = (bar_color or ACCENT) + ";1"
        elif bar_color:
            color = bar_color
        else:
            color = GRAY
        wd_cells.append(c(color, wd))
        day_cells.append(c(color, day_cell))
    return "".join(wd_cells), "".join(day_cells)


parts = []  # list of (text, bg)

if SEG.get("month"):
    arrow, col = trend(month_cost, month_prev_cost)
    value_str = c(col + ";1", f"${month_cost:.2f}")
    arrow_str = c(col + ";1", arrow)
    extras = []
    if SEG.get("remaining"):
        extras.append(f"{c(GRAY, 'SOBRA')} {c(LIGHT, f'${remaining:.2f}')}")
    if SEG.get("reset"):
        extras.append(f"{c(GRAY, 'RESET')} {c(ACCENT, reset_str)}")
    tail = f"{mid}{mid.join(extras)}" if extras else ""
    parts.append((
        f"{c(GRAY, 'MÊS')} {value_str}{slash}{c(GRAY, f'${MONTHLY_LIMIT:.0f}')} {arrow_str}{tail}",
        BG,
    ))

if SEG.get("week"):
    arrow, col = trend(week_cost, week_prev_cost)
    parts.append((metric(f"{DAYS}D ÚTEIS", week_cost, arrow, col), BG))

if SEG.get("today"):
    arrow, col = trend(today_cost, yesterday_cost)
    parts.append((metric("HOJE", today_cost, arrow, col), BG))

tpm_overload = False
tpm_text = ""
if SEG.get("tpm") and avg_tpm > 0:
    tpm_overload = current_tpm > avg_tpm * OVERLOAD
    if tpm_overload:
        cur_col = RED
    elif current_tpm > avg_tpm * (1 + TOL):
        cur_col = YELLOW
    elif current_tpm < avg_tpm * (1 - TOL):
        cur_col = GREEN
    else:
        cur_col = LIGHT
    cur_str = c(cur_col + ";1", fmt_tpm(current_tpm))
    avg_str = c(LIGHT, fmt_tpm(avg_tpm))
    status_txt = "sobrecarga" if tpm_overload else "média 5d"
    status_col = RED if tpm_overload else GRAY
    tpm_text = (
        f"{c(GRAY, 'TPM')} {cur_str} {c(GRAY, 'agora')}{slash}"
        f"{avg_str} {c(status_col, status_txt)}"
    )

if SEG.get("branch") and branch_name:
    if btokens > 0:
        parts.append((
            f"{c(GRAY, 'BRANCH')} {c(PINK + ';3', abbrev_branch(branch_name, BRANCH_MAX))}{mid}"
            f"{c(LIGHT, fmt_tokens(btokens))} {c(GRAY, 'tokens')}{mid}"
            f"{c(TEAL + ';1', f'${bcost:.2f}')} {c(GRAY, 'gasto')}",
            BG,
        ))
    else:
        parts.append((f"{c(GRAY, 'BRANCH')} {c(PINK + ';3', abbrev_branch(branch_name, BRANCH_MAX))}", BG))

PREFIX_BG = "48;5;236"
LETTER_BGS = [
    "48;5;88",    # vinho
    "48;5;130",   # âmbar
    "48;5;22",    # verde escuro
    "48;5;31",    # teal
    "48;5;24",    # azul
    "48;5;55",    # violeta
    "48;5;94",    # marrom
    "48;5;60",    # índigo
    "48;5;53",    # roxo
    "48;5;18",    # navy
]
_letter_offset = (current_tpm // 500 + btokens // 1000) % len(LETTER_BGS)
_daily_cost_chars = []
for _i, _ch in enumerate("DAILY COST"):
    if _ch == " ":
        _daily_cost_chars.append(" ")
    else:
        _bg = LETTER_BGS[(_i + _letter_offset) % len(LETTER_BGS)]
        _daily_cost_chars.append(f"\033[{_bg};38;5;252;1m{_ch}\033[0m")
prefix_inner = (
    c(GREEN + ";1", "$$") + " "
    + "".join(_daily_cost_chars) + " "
    + c(GREEN + ";1", "$$")
)
prefix = apply_bg(prefix_inner, PREFIX_BG)
if parts:
    boxed = [apply_bg(text, bg_code) for text, bg_code in parts]
    print(f"{prefix}  {sep.join(boxed)}")
else:
    print(prefix)

if SEG.get("tpm_chart"):
    chart_rows, peak_v, n_days, day_colors = daily_chart(daily, today, COEF)
    print(" ")
    ax_top = c(DEEP_GRAY, "┤")
    ax_mid = c(DEEP_GRAY, "│")
    corner = c(DEEP_GRAY, "└")
    wd_line, day_line = x_axis_days(today, n_days, today.day, day_colors)

    def fmt_y(v):
        if v >= 100:
            return f"${v:.0f}"
        return f"${v:.1f}"

    y_strs = [fmt_y(peak_v), fmt_y(peak_v * 2 / 3), fmt_y(peak_v / 3)]
    y_width = max(len(s) for s in y_strs)
    y_labels = [c(GRAY, " " + s.rjust(y_width)) for s in y_strs]
    zero_label = c(GRAY, " " + "$0.0".rjust(y_width))

    legend_plain = "   ■ excesso  ■ médio  ■ baixo  ■ vazio"
    legend = "   " + "  ".join([
        f"{c(RED, '■')} {c(GRAY, 'excesso')}",
        f"{c(YELLOW, '■')} {c(GRAY, 'médio')}",
        f"{c(GREEN, '■')} {c(GRAY, 'baixo')}",
        f"{c(DEEP_GRAY, '■')} {c(GRAY, 'vazio')}",
    ])

    print(f"{ax_top}{chart_rows[0]}{y_labels[0]}")
    print(f"{ax_mid}{chart_rows[1]}{y_labels[1]}")
    print(f"{ax_mid}{chart_rows[2]}{y_labels[2]}")
    print(f"{corner}{wd_line}{zero_label}{legend}")
    if tpm_text:
        zero_w = 1 + y_width
        pad_w = zero_w + len(legend_plain) + 13
        tpm_boxed = apply_bg(tpm_text, BG_WARN if tpm_overload else BG)
        print(f" {day_line}{' ' * pad_w}{tpm_boxed}")
    else:
        print(f" {day_line}")
