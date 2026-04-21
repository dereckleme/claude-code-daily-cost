#!/usr/bin/env python3
"""Aggregate Claude Code token usage & cost for the last N days from session JSONL files."""
import json
import os
import glob
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# USD per 1M tokens. Update if pricing changes.
PRICING = {
    "claude-opus-4-7":        {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-opus-4-6":        {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-opus-4-5":        {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-opus-4-1":        {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-opus-4":          {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-sonnet-4-6":      {"in":  3.00, "out": 15.00, "cw5m":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-sonnet-4-5":      {"in":  3.00, "out": 15.00, "cw5m":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-sonnet-4":        {"in":  3.00, "out": 15.00, "cw5m":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-haiku-4-5":       {"in":  1.00, "out":  5.00, "cw5m":  1.25, "cw1h":  2.00, "cr": 0.10},
    "claude-3-5-sonnet":      {"in":  3.00, "out": 15.00, "cw5m":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-3-5-haiku":       {"in":  0.80, "out":  4.00, "cw5m":  1.00, "cw1h":  1.60, "cr": 0.08},
}
DEFAULT_PRICE = {"in": 3.00, "out": 15.00, "cw5m": 3.75, "cw1h": 6.00, "cr": 0.30}


def price_for(model: str):
    if not model:
        return DEFAULT_PRICE
    for key, price in PRICING.items():
        if model.startswith(key):
            return price
    return DEFAULT_PRICE


def cost_for(model: str, usage: dict) -> float:
    p = price_for(model)
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cread = usage.get("cache_read_input_tokens", 0) or 0
    cw = usage.get("cache_creation", {}) or {}
    cw5 = cw.get("ephemeral_5m_input_tokens", 0) or 0
    cw1 = cw.get("ephemeral_1h_input_tokens", 0) or 0
    if not cw5 and not cw1:
        cw5 = usage.get("cache_creation_input_tokens", 0) or 0
    total = (
        inp  * p["in"]   +
        out  * p["out"]  +
        cread * p["cr"]  +
        cw5  * p["cw5m"] +
        cw1  * p["cw1h"]
    ) / 1_000_000
    return total


def total_tokens(usage: dict) -> int:
    return (
        (usage.get("input_tokens") or 0)
        + (usage.get("output_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
    )


WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def bar(value: float, max_value: float, width: int = 30) -> str:
    if max_value <= 0:
        return ""
    filled = int(round((value / max_value) * width))
    return "█" * filled + "░" * (width - filled)


def business_days(days: int, today=None):
    today = today or datetime.now().date()
    ordered = []
    cursor = today
    while len(ordered) < days:
        if cursor.weekday() < 5:
            ordered.append(cursor)
        cursor -= timedelta(days=1)
    ordered.reverse()
    return ordered


def scan(allowed_days):
    """Scan Claude Code JSONLs once; return per-day aggregates and per-minute tokens."""
    allowed = set(allowed_days)
    seen_ids = set()
    daily = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "msgs": 0})
    minutes = defaultdict(int)
    pattern = os.path.expanduser("~/.claude/projects/**/*.jsonl")
    for fp in glob.glob(pattern, recursive=True):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    ts = obj.get("timestamp")
                    if not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                    except ValueError:
                        continue
                    day = dt.date()
                    if day not in allowed:
                        continue
                    mid = msg.get("id")
                    key = (mid, fp)
                    if mid and key in seen_ids:
                        continue
                    seen_ids.add(key)
                    model = msg.get("model", "")
                    toks = total_tokens(usage)
                    daily[day]["cost"] += cost_for(model, usage)
                    daily[day]["tokens"] += toks
                    daily[day]["msgs"] += 1
                    minute_key = dt.replace(second=0, microsecond=0)
                    minutes[minute_key] += toks
        except (OSError, PermissionError):
            continue
    return {"daily": daily, "minutes": minutes}


def aggregate(allowed_days):
    return scan(allowed_days)["daily"]


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    ordered = business_days(days)
    daily = aggregate(ordered)
    max_cost = max((daily[d]["cost"] for d in ordered), default=0.0) or 0.0

    print(f"\n  Claude Code — últimos {days} dias úteis  (custo em USD, tokens totais)")
    print("  " + "─" * 64)

    total_cost = 0.0
    total_toks = 0
    for d in ordered:
        entry = daily[d]
        c = entry["cost"]
        t = entry["tokens"]
        total_cost += c
        total_toks += t
        weekday = WEEKDAYS_PT[d.weekday()]
        b = bar(c, max_cost, width=28)
        tok_str = f"{t/1_000_000:.2f}M" if t >= 1_000_000 else f"{t/1_000:.1f}k"
        print(f"  {d.isoformat()} {weekday}  ${c:6.2f}  {b}  {tok_str:>7} tok  ({entry['msgs']} msg)")

    print("  " + "─" * 64)
    tot_tok_str = f"{total_toks/1_000_000:.2f}M" if total_toks >= 1_000_000 else f"{total_toks/1_000:.1f}k"
    print(f"  TOTAL{' ' * 21}${total_cost:6.2f}{' ' * 32}{tot_tok_str:>7} tok")
    print()


if __name__ == "__main__":
    main()
