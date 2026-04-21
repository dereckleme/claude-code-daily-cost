#!/usr/bin/env python3
"""Print Claude Code token/cost for current cwd + git branch. Used by starship custom module."""
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cost import cost_for, total_tokens, resolve_projects_dir

CACHE_TTL_SEC = 10
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_coef():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return float(json.load(f).get("plan_coefficient", 0.4419))
    except Exception:
        return 0.4419


def current_branch(cwd=None):
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=0.5, cwd=cwd,
        )
        if r.returncode == 0:
            b = r.stdout.strip()
            return b or None
    except Exception:
        pass
    return None


def aggregate(cwd, branch, projects_dir=None):
    cost = 0.0
    tokens = 0
    seen = set()
    encoded = cwd.replace("/", "-")
    store = projects_dir or resolve_projects_dir()
    base = os.path.join(store, encoded)
    if not os.path.isdir(base):
        return cost, tokens
    try:
        entries = os.listdir(base)
    except OSError:
        return cost, tokens
    for name in entries:
        if not name.endswith(".jsonl"):
            continue
        fp = os.path.join(base, name)
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
                    if obj.get("cwd") != cwd:
                        continue
                    if obj.get("gitBranch") != branch:
                        continue
                    msg = obj.get("message") or {}
                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    mid = msg.get("id")
                    key = (mid, fp)
                    if mid and key in seen:
                        continue
                    seen.add(key)
                    cost += cost_for(msg.get("model", ""), usage)
                    tokens += total_tokens(usage)
        except OSError:
            continue
    return cost, tokens


def fmt_tokens(t):
    if t >= 1_000_000:
        return f"{t/1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t/1_000:.1f}k"
    return str(t)


def main():
    cwd = os.getcwd()
    branch = current_branch()
    if not branch:
        return
    key = hashlib.md5(f"{cwd}|{branch}".encode()).hexdigest()[:12]
    cache_fp = f"/tmp/claude_cost_branch_{key}"
    try:
        if os.path.exists(cache_fp) and time.time() - os.path.getmtime(cache_fp) < CACHE_TTL_SEC:
            with open(cache_fp, "r", encoding="utf-8") as f:
                sys.stdout.write(f.read())
            return
    except OSError:
        pass
    coef = load_coef()
    cost, tokens = aggregate(cwd, branch)
    out = f"{fmt_tokens(tokens)} tok · ${cost * coef:.2f}" if tokens > 0 else ""
    try:
        with open(cache_fp, "w", encoding="utf-8") as f:
            f.write(out)
    except OSError:
        pass
    sys.stdout.write(out)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
