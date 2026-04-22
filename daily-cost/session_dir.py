"""Resolve the active Claude Code config dir for the current session.

O usuário pode ter múltiplos dirs (`~/.claude`, `~/.claude-pessoal`, ...).
A sessão ativa é resolvida nesta ordem:

  1. `transcript_path` do stdin (statusline) — fonte definitiva da sessão.
  2. `$CLAUDE_CONFIG_DIR` env var — override explícito do usuário.
  3. `lsof` no processo claude ancestral — qual `.claude*/` ele tem aberto.
  4. mtime dos `*.jsonl` — config dir com transcript mais recente.
  5. Fallback `$HOME/.claude`.

Nenhum path é hardcoded a uma variante específica.
"""
import os
import re
import subprocess


_LSOF_PATH_RE = re.compile(r"(/[^\s]*?/\.claude[^/\s]*)/")


def _claude_dir_from_lsof_line(line: str):
    m = _LSOF_PATH_RE.search(line)
    if not m:
        return None
    d = m.group(1)
    return d if os.path.isdir(d) else None


def _parent_pid(pid):
    try:
        out = subprocess.check_output(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            stderr=subprocess.DEVNULL, timeout=1,
        ).decode().strip()
        return int(out) if out.isdigit() else None
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _process_command(pid):
    try:
        return subprocess.check_output(
            ["ps", "-o", "command=", "-p", str(pid)],
            stderr=subprocess.DEVNULL, timeout=1,
        ).decode().strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _lsof_config_dir(pid):
    try:
        out = subprocess.check_output(
            ["lsof", "-p", str(pid)],
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode(errors="replace")
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return None
    for line in out.splitlines():
        d = _claude_dir_from_lsof_line(line)
        if d:
            return d
    return None


def _detect_via_ancestor():
    """Sobe a cadeia de PIDs procurando um processo `claude` e pergunta ao lsof
    qual `.claude*/` ele tem aberto."""
    pid = os.getpid()
    for _ in range(8):
        parent = _parent_pid(pid)
        if not parent or parent == 1:
            break
        cmd = _process_command(parent)
        if cmd and "claude" in cmd.lower():
            d = _lsof_config_dir(parent)
            if d:
                return d
        pid = parent
    return None


def _latest_jsonl_mtime(projects_dir):
    latest = -1.0
    try:
        for entry in os.listdir(projects_dir):
            sub = os.path.join(projects_dir, entry)
            if not os.path.isdir(sub):
                continue
            try:
                for f in os.listdir(sub):
                    if not f.endswith(".jsonl"):
                        continue
                    try:
                        mt = os.path.getmtime(os.path.join(sub, f))
                    except OSError:
                        continue
                    if mt > latest:
                        latest = mt
            except OSError:
                continue
    except OSError:
        pass
    return latest


def _detect_via_mtime(home):
    best = None
    best_mt = -1.0
    try:
        for entry in os.listdir(home):
            if not entry.startswith(".claude"):
                continue
            projects = os.path.join(home, entry, "projects")
            if not os.path.isdir(projects):
                continue
            mt = _latest_jsonl_mtime(projects)
            if mt > best_mt:
                best_mt = mt
                best = os.path.join(home, entry)
    except OSError:
        pass
    return best


def resolve_config_dir():
    """Retorna o config dir absoluto do Claude Code ativo nesta sessão."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        env = os.path.expanduser(env)
        if os.path.isdir(env):
            return env
    viaproc = _detect_via_ancestor()
    if viaproc:
        return viaproc
    home = os.path.expanduser("~")
    viamt = _detect_via_mtime(home)
    if viamt:
        return viamt
    return os.path.join(home, ".claude")


def resolve_projects_dir(stdin_ctx=None):
    """Resolve o `projects/` da sessão ativa.

    Prioridade: transcript_path (stdin) > resolve_config_dir().
    """
    if stdin_ctx:
        tp = stdin_ctx.get("transcript_path")
        if tp:
            return os.path.dirname(os.path.dirname(tp))
    return os.path.join(resolve_config_dir(), "projects")


_LABEL_SAFE_RE = re.compile(r"[^a-z0-9_-]+")


def env_label(config_dir):
    """Slug curto que identifica um config dir (`~/.claude-pessoal` → `pessoal`).

    Usado pelo proxy pra separar state por env quando a mesma instância
    atende múltiplos `.claude*/`. `.claude` (ou qualquer fallback) vira
    `default`.
    """
    if not config_dir:
        return "default"
    name = os.path.basename(os.path.normpath(config_dir)).lower()
    if name.startswith(".claude-"):
        tail = name[len(".claude-"):]
    elif name.startswith(".claude"):
        tail = name[len(".claude"):]
    else:
        tail = name
    tail = _LABEL_SAFE_RE.sub("-", tail).strip("-")
    return tail or "default"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "label":
        print(env_label(resolve_config_dir()))
    else:
        print(resolve_config_dir())
