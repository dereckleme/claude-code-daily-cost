#!/usr/bin/env bash
# Sobe o proxy se não estiver vivo. Idempotente. Escreve PID e aguarda porta.
#
# Uso: ensure-proxy.sh [port]
# Env: CLAUDE_USAGE_PROXY_PORT (default 8765)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_PY="$HERE/proxy.py"
PID_FILE="$HERE/proxy.pid"
LOG_FILE="$HERE/proxy.log"
PORT="${1:-${CLAUDE_USAGE_PROXY_PORT:-8765}}"

alive() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_responding() {
  # /_usage_proxy_health retornando 2xx = é *o nosso* proxy (path é único)
  curl -s -o /dev/null --connect-timeout 1 -w "%{http_code}" \
    "http://127.0.0.1:$PORT/_usage_proxy_health" 2>/dev/null | grep -qE '^2[0-9][0-9]$'
}

# Proxy já respondendo — reusa. Cobre o caso de outra instância .claude*
# ter subido o daemon (mesmo proxy atende múltiplos envs via path prefix).
if port_responding; then
  if alive; then
    echo "proxy já no ar (pid $(cat "$PID_FILE"), port $PORT)"
  else
    echo "proxy já no ar (compartilhado, port $PORT)"
  fi
  exit 0
fi

# Limpa estado stale
rm -f "$PID_FILE"

# Porta ocupada mas não é o nosso proxy (health falhou) — não sobrescreve
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "erro: porta $PORT ocupada por outro processo (não é o proxy)" >&2
  echo "resolva o conflito ou use CLAUDE_USAGE_PROXY_PORT=<outra_porta>" >&2
  exit 1
fi

# Sobe daemon desacoplado do TTY (sobrevive fechar terminal)
CLAUDE_USAGE_PROXY_PORT="$PORT" \
  nohup python3 "$PROXY_PY" >>"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
disown || true

# Aguarda até 3s pela porta responder
for _ in $(seq 1 30); do
  if port_responding; then
    echo "proxy iniciado (pid $(cat "$PID_FILE"), port $PORT)"
    exit 0
  fi
  sleep 0.1
done

echo "erro: proxy não respondeu em 3s — checar $LOG_FILE" >&2
exit 1
