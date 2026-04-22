#!/usr/bin/env bash
# Mata o proxy e limpa arquivos de estado.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$HERE/proxy.pid"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    # Aguarda até 1s, depois força
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    kill -9 "$pid" 2>/dev/null || true
    echo "proxy parado (pid $pid)"
  else
    echo "proxy não estava rodando"
  fi
  rm -f "$PID_FILE" "$HERE/proxy.session"
else
  echo "proxy não estava rodando"
fi
