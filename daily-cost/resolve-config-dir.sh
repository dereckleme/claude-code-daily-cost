#!/usr/bin/env bash
# Imprime o config dir Claude Code da sessão ativa (~/.claude, ~/.claude-pessoal, ...).
# Nunca falha — sempre imprime um caminho (fallback $HOME/.claude).
#
# Prioridade:
#   1. $CLAUDE_CONFIG_DIR (se setado e existir)
#   2. lsof no processo claude ancestral — qual .claude*/ ele tem aberto
#   3. mtime dos *.jsonl — config dir com transcript mais recente
#   4. $HOME/.claude
set -u

if [[ -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
  expanded="${CLAUDE_CONFIG_DIR/#\~/$HOME}"
  if [[ -d "$expanded" ]]; then
    echo "$expanded"
    exit 0
  fi
fi

pid=$$
for _ in 1 2 3 4 5 6 7 8; do
  parent=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  [[ -z "$parent" || "$parent" == "0" || "$parent" == "1" ]] && break
  cmd=$(ps -o command= -p "$parent" 2>/dev/null || true)
  if [[ -n "$cmd" && "$cmd" == *claude* ]]; then
    fallback=""
    while IFS= read -r d; do
      [[ -d "$d" ]] || continue
      if [[ "$(dirname "$d")" == "$HOME" ]]; then
        echo "$d"
        exit 0
      fi
      [[ -z "$fallback" ]] && fallback="$d"
    done < <(lsof -p "$parent" 2>/dev/null \
      | awk 'match($0, /\/[^ ]*\/\.claude[^\/ ]*/) { print substr($0, RSTART, RLENGTH) }' \
      | sort -u)
    if [[ -n "$fallback" ]]; then
      echo "$fallback"
      exit 0
    fi
  fi
  pid=$parent
done

best=""
best_mt=0
for d in "$HOME"/.claude*; do
  [[ -d "$d/projects" ]] || continue
  mt=$(find "$d/projects" -name '*.jsonl' -type f -print0 2>/dev/null \
    | xargs -0 stat -f '%m' 2>/dev/null \
    | sort -n | tail -1)
  [[ -z "$mt" ]] && continue
  if (( ${mt%.*} > best_mt )); then
    best_mt=${mt%.*}
    best="$d"
  fi
done
echo "${best:-$HOME/.claude}"
