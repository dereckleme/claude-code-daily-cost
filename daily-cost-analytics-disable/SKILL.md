---
name: daily-cost-analytics-disable
description: Desliga o painel completo do daily-cost — mata o proxy HTTP local, remove ANTHROPIC_BASE_URL do settings.json do config dir ativo e desliga todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit).
---

Inverso de `/daily-cost-analytics-enable`. Deixa o Claude Code falando direto com `api.anthropic.com` e oculta todo o painel do statusline.

## Como executar

Resolva o config dir e rode o script Python atômico em **um único passo**:

```bash
CCD="$(bash "$HOME/.claude/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
      || bash "$HOME/.claude-pessoal/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
      || echo "$HOME/.claude")"
python3 "$CCD/skills/daily-cost/disable.py" $ARGS
```

Onde `$ARGS` é vazio por padrão ou `limpar` se o usuário passou esse argumento.

O script faz tudo atomicamente e mata o proxy **5 segundos após retornar** — o proxy ainda está vivo quando o script termina, garantindo que esta sessão consiga enviar a resposta final sem erro de conexão.

## O que o script faz internamente

1. Resolve o config dir ativo (mesma lógica do `resolve-config-dir.sh`).
2. Desliga todos os segmentos em `config.json` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit` → `false`).
3. Remove `ANTHROPIC_BASE_URL` de `settings.json` (se apontar para `127.0.0.1`; se for outro destino, avisa e não mexe).
4. Agenda o kill do proxy em background (5s de delay via subprocess `bash -c "sleep 5 && kill …"`).
5. Se `limpar` foi passado: remove também `proxy.pid`, `proxy.session`, `proxy.log`, `proxy_*.log`, `usage-state.json`.

## Argumentos aceitos

- Sem argumento: desativa mantendo logs e state pra consulta.
- `limpar`: desativa e apaga logs/state/pid/session.

## Resposta final

Mostre a saída do script (já formatada) e reforce: **"Reinicie o Claude Code para voltar a falar direto com api.anthropic.com."**
