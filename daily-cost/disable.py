#!/usr/bin/env python3
"""
Desliga o daily-cost de forma atômica:
  1. Desliga todos os segmentos em config.json
  2. Remove ANTHROPIC_BASE_URL de settings.json
  3. Mata o proxy com 5s de delay em background

O delay garante que a sessão LLM atual consiga enviar a resposta final
antes de o proxy morrer.

Uso:
  python3 disable.py            # desativa, mantém logs
  python3 disable.py limpar     # desativa e apaga logs/state/pid/session
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

SEGMENTS = ["today", "week", "month", "reset", "branch", "tpm", "tpm_chart", "limit"]
PROXY_KILL_DELAY = 5  # segundos


# ---------------------------------------------------------------------------
# Config dir resolution (equivalente ao resolve-config-dir.sh)
# ---------------------------------------------------------------------------

def _find_claude_pid() -> int | None:
    pid = os.getpid()
    for _ in range(8):
        try:
            ppid = int(subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                text=True, stderr=subprocess.DEVNULL
            ).strip())
        except Exception:
            break
        if ppid in (0, 1, pid):
            break
        try:
            cmd = subprocess.check_output(
                ["ps", "-o", "command=", "-p", str(ppid)],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            if "claude" in cmd.lower():
                return ppid
        except Exception:
            pass
        pid = ppid
    return None


def resolve_config_dir() -> Path:
    home = Path.home()

    # 1. $CLAUDE_CONFIG_DIR
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if env_dir:
        p = Path(env_dir.replace("~", str(home)))
        if p.is_dir():
            return p

    # 2. lsof no processo claude ancestral
    claude_pid = _find_claude_pid()
    if claude_pid:
        try:
            lsof_out = subprocess.check_output(
                ["lsof", "-p", str(claude_pid)],
                text=True, stderr=subprocess.DEVNULL
            )
            candidates: list[Path] = []
            for m in re.finditer(r"(/[^ ]*/.claude[^/ ]*)", lsof_out):
                d = Path(m.group(1))
                if d.is_dir():
                    candidates.append(d)
            # dedupe preservando ordem
            seen: set[Path] = set()
            unique: list[Path] = []
            for d in candidates:
                if d not in seen:
                    seen.add(d)
                    unique.append(d)
            for d in unique:
                if d.parent == home:
                    return d
            if unique:
                return unique[0]
        except Exception:
            pass

    # 3. mtime dos *.jsonl — config dir com transcript mais recente
    best: Path | None = None
    best_mt: float = 0
    for d in home.glob(".claude*"):
        if not (d / "projects").is_dir():
            continue
        for jsonl in d.glob("projects/**/*.jsonl"):
            mt = jsonl.stat().st_mtime
            if mt > best_mt:
                best_mt = mt
                best = d
    return best or (home / ".claude")


# ---------------------------------------------------------------------------
# Operações
# ---------------------------------------------------------------------------

def disable_segments(config_path: Path) -> str:
    if not config_path.exists():
        return f"config.json não encontrado em {config_path}"
    with open(config_path) as f:
        data = json.load(f)
    segs = data.setdefault("segments", {})
    for key in SEGMENTS:
        segs[key] = False
    with open(config_path, "w") as f:
        json.dump(data, f, indent=4)
    return "segmentos desligados"


def remove_base_url(settings_path: Path) -> str:
    if not settings_path.exists():
        return f"settings.json não encontrado em {settings_path}"
    with open(settings_path) as f:
        data = json.load(f)
    env = data.get("env", {})
    base_url = env.get("ANTHROPIC_BASE_URL", "")
    if not base_url:
        return "ANTHROPIC_BASE_URL não estava definida"
    if not base_url.startswith("http://127.0.0.1"):
        return f"ANTHROPIC_BASE_URL={base_url!r} não é do daily-cost — não modificado"
    del env["ANTHROPIC_BASE_URL"]
    if not env:
        data.pop("env", None)
    else:
        data["env"] = env
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=4)
    return f"ANTHROPIC_BASE_URL removida ({base_url})"


def _kill_pid(pid: int, pid_file: Path) -> None:
    """Mata o processo e limpa arquivos de estado."""
    session_file = pid_file.parent / "proxy.session"
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except ProcessLookupError:
        pass
    finally:
        for f in (pid_file, session_file):
            try:
                f.unlink()
            except FileNotFoundError:
                pass


def schedule_proxy_kill(pid_file: Path) -> str:
    """Agenda kill do proxy em background após PROXY_KILL_DELAY segundos."""
    if not pid_file.exists():
        return "proxy não estava rodando"

    pid_str = pid_file.read_text().strip()
    if not pid_str:
        pid_file.unlink(missing_ok=True)
        return "proxy não estava rodando"

    try:
        pid = int(pid_str)
        os.kill(pid, 0)  # verifica se está vivo
    except (ValueError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        (pid_file.parent / "proxy.session").unlink(missing_ok=True)
        return "proxy não estava rodando"

    # Subprocess independente que dorme e mata — não herda o processo pai
    kill_cmd = (
        f"sleep {PROXY_KILL_DELAY} && "
        f"kill {pid} 2>/dev/null; "
        f"sleep 1 && kill -9 {pid} 2>/dev/null; "
        f"rm -f {pid_file} {pid_file.parent / 'proxy.session'}"
    )
    subprocess.Popen(
        ["bash", "-c", kill_cmd],
        start_new_session=True,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return f"proxy será parado em {PROXY_KILL_DELAY}s (pid {pid})"


def clean_artifacts(proxy_dir: Path) -> str:
    removed: list[str] = []
    for name in ("proxy.pid", "proxy.session", "proxy.log"):
        p = proxy_dir / name
        if p.exists() or p.is_symlink():
            p.unlink(missing_ok=True)
            removed.append(name)
    for log in proxy_dir.glob("proxy_*.log"):
        log.unlink(missing_ok=True)
        removed.append(log.name)
    usage = proxy_dir / "usage-state.json"
    if usage.exists():
        usage.unlink()
        removed.append("usage-state.json")
    if removed:
        return f"artefatos removidos: {', '.join(removed)}"
    return "nenhum artefato para remover"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    do_clean = "limpar" in args or "--clean" in args

    ccd = resolve_config_dir()
    print(f"config dir: {ccd}")

    config_path = ccd / "skills" / "daily-cost" / "config.json"
    settings_path = ccd / "settings.json"
    proxy_dir = ccd / "skills" / "daily-cost" / "proxy"
    pid_file = proxy_dir / "proxy.pid"

    print(disable_segments(config_path))
    print(remove_base_url(settings_path))
    print(schedule_proxy_kill(pid_file))

    if do_clean:
        print(clean_artifacts(proxy_dir))

    print()
    print("Pronto. Reinicie o Claude Code para voltar a falar direto com api.anthropic.com.")


if __name__ == "__main__":
    main()
