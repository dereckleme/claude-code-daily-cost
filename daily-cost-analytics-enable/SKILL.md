---
name: daily-cost-analytics-enable
description: Liga o painel completo do daily-cost — todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit) + proxy HTTP local que captura headers anthropic-ratelimit-* pra mostrar cota de 5h em tempo real. Edita ~/.claude/settings.json e requer reiniciar o Claude Code.
---

Skill única pra ligar **tudo** do daily-cost de uma vez: segmentos do statusline + proxy de tracking de cota.

## O que esta skill faz

1. Liga todos os segmentos em `~/.claude/skills/daily-cost/config.json`.
2. Sobe o proxy HTTP local (porta 8765 por padrão) via `~/.claude/skills/daily-cost/proxy/ensure-proxy.sh`. O proxy captura só os headers `anthropic-ratelimit-*` e `anthropic-organization-*` — body de request/response nunca é lido nem persistido.
3. Insere `env.ANTHROPIC_BASE_URL=http://127.0.0.1:<porta>` em `~/.claude/settings.json` pra o Claude Code rotear tráfego pelo proxy.
4. Avisa que é preciso reiniciar o Claude Code pra a env var entrar em vigor.

## Transparência

- **O que o proxy vê**: 100% do tráfego Claude Code → Anthropic (mensagens, tool calls, bearer). Inevitável pra qualquer proxy.
- **O que persiste em disco**: só `usage-state.json` com os headers na allowlist (`anthropic-ratelimit-*`, `anthropic-organization-*`, `retry-after`, `anthropic-request-id`). Allowlist hardcoded em `proxy/proxy.py` (`CAPTURED_PREFIXES`, `CAPTURED_EXACT`).
- **Rede**: proxy escuta só em 127.0.0.1.

## Passos que o Claude vai executar

1. **Ligar segmentos** editando `~/.claude/skills/daily-cost/config.json` → bloco `segments` com todos os campos `true` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit`).

2. **Subir proxy**: `bash ~/.claude/skills/daily-cost/proxy/ensure-proxy.sh`. Se a porta 8765 estiver ocupada, o script aborta — escolha outra via `CLAUDE_USAGE_PROXY_PORT=<porta> bash ensure-proxy.sh <porta>`.

3. **Health check**: `curl -s http://127.0.0.1:<porta>/_usage_proxy_health` deve retornar `{"ok": true, "state": {...}}`.

4. **Inserir ANTHROPIC_BASE_URL** em `~/.claude/settings.json` no bloco `env`:
   ```json
   { "env": { "ANTHROPIC_BASE_URL": "http://127.0.0.1:8765" } }
   ```
   Se já existia apontando pra outro lugar (Bedrock/Vertex/outro proxy), **pergunte** antes de sobrescrever.

5. **Avisar**: "⚠️ Reinicie Claude Code pra ativar o tracking. A env var só entra em vigor em sessões novas."

6. Rodar `echo '{}' | python3 ~/.claude/skills/daily-cost/statusline.py` e mostrar a saída atual em bloco de código.

## Argumentos aceitos

- Sem argumento (default): porta 8765.
- `porta=<N>`: porta customizada (ex.: `/daily-cost-analytics-enable porta=9999`).

## Ciclo de vida

- **Pós-instalação**: daemon sobrevive fechar terminal (`nohup` + `disown`).
- **Pós-reboot**: daemon morre. Rode `/daily-cost-analytics-enable` de novo — idempotente.
- **Desinstalação**: use `/daily-cost-analytics-disable`.

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `~/.claude/skills/daily-cost/proxy/proxy.pid` | criado |
| `~/.claude/skills/daily-cost/proxy/proxy.log` | criado (append) |
| `~/.claude/skills/daily-cost/proxy/usage-state.json` | criado/atualizado a cada request |
| `~/.claude/settings.json` | adiciona `env.ANTHROPIC_BASE_URL` |
| `~/.claude/skills/daily-cost/config.json` | seta todos os `segments.*` = `true` |
