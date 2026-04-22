#!/usr/bin/env bash
# Sobe o proxy para esta instância do Claude Code. Idempotente dentro da mesma
# sessão; se detectar uma sessão diferente, mata o proxy antigo e sobe um novo.
# Se a porta solicitada estiver ocupada, avança automaticamente para a próxima
# porta livre e persiste o valor resolvido em config.json e settings.json.
#
# Uso: ensure-proxy.sh [port]
# Prioridade de porta: arg[1] > CLAUDE_USAGE_PROXY_PORT > config.json > 8765
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_PY="$HERE/proxy.py"
PID_FILE="$HERE/proxy.pid"
SESSION_FILE="$HERE/proxy.session"
CONFIG_JSON="$HERE/../config.json"
SETTINGS_JSON="$HERE/../../../settings.json"

# Detecta o PID do processo Claude Code ancestral percorrendo a árvore de processos.
find_claude_pid() {
  local pid=$$
  while [[ "$pid" -gt 1 ]]; do
    local cmd
    cmd=$(ps -o comm= -p "$pid" 2>/dev/null || echo "")
    if [[ "$cmd" == *claude* ]]; then
      echo "$pid"
      return 0
    fi
    local ppid
    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || echo 1)
    [[ "$ppid" == "$pid" ]] && break  # evita loop se ppid == pid (PID 1)
    pid="$ppid"
  done
  echo ""
}

CLAUDE_PID="$(find_claude_pid)"

# Resolve porta inicial: arg > env > config.json > 8765
config_port() {
  [[ -f "$CONFIG_JSON" ]] || { echo ""; return; }
  python3 -c "
import json, sys
try:
    d = json.load(open('$CONFIG_JSON'))
    print(d.get('proxy_port', ''))
except Exception:
    print('')
" 2>/dev/null || echo ""
}

_config_port="$(config_port)"
PORT="${1:-${CLAUDE_USAGE_PROXY_PORT:-${_config_port:-8765}}}"

# Aponta LOG_FILE para um arquivo timestamped; cria symlink proxy.log → atual
new_log_file() {
  local ts
  ts="$(date '+%Y%m%dT%H%M%S')"
  local log="$HERE/proxy_${ts}.log"
  ln -sf "$(basename "$log")" "$HERE/proxy.log"
  echo "$log"
}

alive() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_responding() {
  local p="${1:-$PORT}"
  curl -s -o /dev/null --connect-timeout 1 -w "%{http_code}" \
    "http://127.0.0.1:$p/_usage_proxy_health" 2>/dev/null | grep -qE '^2[0-9][0-9]$'
}

same_session() {
  [[ -f "$SESSION_FILE" ]] || return 1
  [[ -z "$CLAUDE_PID" ]] && return 1  # sem PID detectado → não reutiliza
  local stored
  stored="$(cat "$SESSION_FILE" 2>/dev/null || echo)"
  [[ "$stored" == "$CLAUDE_PID" ]]
}

# Persiste porta resolvida em config.json e settings.json do env.
persist_port() {
  local port="$1"
  [[ -f "$CONFIG_JSON" ]] && python3 - "$CONFIG_JSON" "$port" <<'PYEOF'
import json, sys
path, port = sys.argv[1], int(sys.argv[2])
with open(path) as f: d = json.load(f)
d['proxy_port'] = port
with open(path, 'w') as f: json.dump(d, f, indent=4)
PYEOF
  [[ -f "$SETTINGS_JSON" ]] && python3 - "$SETTINGS_JSON" "$port" <<'PYEOF'
import json, sys
path, port = sys.argv[1], int(sys.argv[2])
with open(path) as f: d = json.load(f)
d.setdefault('env', {})['ANTHROPIC_BASE_URL'] = f'http://127.0.0.1:{port}'
with open(path, 'w') as f: json.dump(d, f, indent=4)
PYEOF
}

# Proxy vivo E mesma sessão → reutiliza
if alive && port_responding "$PORT" && same_session; then
  echo "proxy já no ar para esta sessão (pid $(cat "$PID_FILE"), port $PORT)"
  exit 0
fi

# Proxy de sessão diferente ou stale → mata antes de subir novo
if alive; then
  pid_old="$(cat "$PID_FILE" 2>/dev/null || echo)"
  if [[ -n "$pid_old" ]]; then
    kill "$pid_old" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$pid_old" 2>/dev/null || break
      sleep 0.1
    done
    kill -9 "$pid_old" 2>/dev/null || true
    echo "proxy da sessão anterior encerrado (pid $pid_old)"
  fi
fi

rm -f "$PID_FILE" "$SESSION_FILE"

# Avança para a próxima porta livre — nunca falha por conflito de porta.
while lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  echo "porta $PORT ocupada, tentando $((PORT + 1))..." >&2
  PORT=$((PORT + 1))
done

persist_port "$PORT"

LOG_FILE="$(new_log_file)"

CLAUDE_USAGE_PROXY_PORT="$PORT" \
  nohup python3 "$PROXY_PY" >>"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
[[ -n "$CLAUDE_PID" ]] && echo "$CLAUDE_PID" > "$SESSION_FILE"
disown || true

# Aguarda até 3s pela porta responder
for _ in $(seq 1 30); do
  if port_responding "$PORT"; then
    echo "proxy iniciado (pid $(cat "$PID_FILE"), port $PORT, log $(basename "$LOG_FILE"))"
    exit 0
  fi
  sleep 0.1
done

echo "erro: proxy não respondeu em 3s — checar $LOG_FILE" >&2
exit 1
