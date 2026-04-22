---
name: daily-cost-analytics-enable
description: Liga o painel completo do daily-cost — todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit) + proxy HTTP local que captura headers anthropic-ratelimit-* pra mostrar cota de 5h em tempo real. Edita settings.json do config dir ativo e requer reiniciar o Claude Code.
---

Skill única pra ligar **tudo** do daily-cost de uma vez: segmentos do statusline + proxy de tracking de cota.

## O que esta skill faz

1. Liga todos os segmentos em `$CCD/skills/daily-cost/config.json`.
2. Sobe o proxy HTTP local via `$CCD/skills/daily-cost/proxy/ensure-proxy.sh`. O proxy captura só os headers `anthropic-ratelimit-*` e `anthropic-organization-*` — body de request/response nunca é lido nem persistido.
3. Insere `env.ANTHROPIC_BASE_URL=http://127.0.0.1:<porta>` em `$CCD/settings.json` pra o Claude Code rotear tráfego pelo proxy.
4. Avisa que é preciso reiniciar o Claude Code pra a env var entrar em vigor.

`$CCD` = config dir ativo desta sessão (`~/.claude`, `~/.claude-pessoal`, …). Ver passo 0 abaixo.

## Transparência

- **O que o proxy vê**: 100% do tráfego Claude Code → Anthropic (mensagens, tool calls, bearer). Inevitável pra qualquer proxy.
- **O que persiste em disco**: só `usage-state.json` com os headers na allowlist (`anthropic-ratelimit-*`, `anthropic-organization-*`, `retry-after`, `anthropic-request-id`). Allowlist hardcoded em `proxy/proxy.py` (`CAPTURED_PREFIXES`, `CAPTURED_EXACT`).
- **Rede**: proxy escuta só em 127.0.0.1.

## Passos que o Claude vai executar

0. **Resolver config dir da sessão ativa** — rode o helper e guarde em `CCD`. Todos os passos seguintes usam `$CCD`, **nunca** `~/.claude` hardcoded:
   ```bash
   CCD="$(bash "$HOME/.claude/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || bash "$HOME/.claude-pessoal/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || echo "$HOME/.claude")"
   echo "config dir: $CCD"
   ```
   Se o usuário tem múltiplos `~/.claude*` dirs, o helper detecta qual está ativo via `$CLAUDE_CONFIG_DIR` env, inspeção do processo claude (lsof) ou mtime dos transcripts.

1. **Ligar segmentos** editando `$CCD/skills/daily-cost/config.json` → bloco `segments` com todos os campos `true` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit`).

2. **Determinar a porta** lendo `proxy_port` de `$CCD/skills/daily-cost/config.json` (default `8765`). Se a porta estiver ocupada por um processo que **não** responde ao health check (`/_usage_proxy_health` com 2xx), escolha a próxima porta livre (8766, 8767, …) e salve em `config.json["proxy_port"]`. Se o nosso proxy já estiver respondendo nessa porta, reuse-o.

3. **Subir proxy**: `CLAUDE_USAGE_PROXY_PORT=<porta> bash "$CCD/skills/daily-cost/proxy/ensure-proxy.sh"`.

4. **Health check**: `curl -s http://127.0.0.1:<porta>/_usage_proxy_health` deve retornar `{"ok": true, "state": {...}}`.

5. **Inserir ANTHROPIC_BASE_URL** em `$CCD/settings.json` no bloco `env`:
   ```json
   { "env": { "ANTHROPIC_BASE_URL": "http://127.0.0.1:<porta>" } }
   ```
   Se já existia apontando pra outro lugar (Bedrock/Vertex/outro proxy externo que **não** seja `http://127.0.0.1:*`), **pergunte** antes de sobrescrever.

6. **Avisar**: "⚠️ Reinicie Claude Code pra ativar o tracking. A env var só entra em vigor em sessões novas."

7. Rodar `echo '{}' | python3 "$CCD/skills/daily-cost/statusline.py"` e mostrar a saída atual em bloco de código.

## Argumentos aceitos

- Sem argumento (default): usa `proxy_port` do config.json ou 8765.
- `porta=<N>`: porta customizada (ex.: `/daily-cost-analytics-enable porta=9999`). Salva em `config.json["proxy_port"]`.

## Ciclo de vida

- **Pós-instalação**: daemon sobrevive fechar terminal (`nohup` + `disown`).
- **Pós-reboot**: daemon morre. Rode `/daily-cost-analytics-enable` de novo — idempotente.
- **Desinstalação**: use `/daily-cost-analytics-disable`.

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `$CCD/skills/daily-cost/proxy/proxy.pid` | criado |
| `$CCD/skills/daily-cost/proxy/proxy.log` | criado (append) |
| `$CCD/skills/daily-cost/proxy/usage-state.json` | criado/atualizado a cada request |
| `$CCD/settings.json` | adiciona `env.ANTHROPIC_BASE_URL` |
| `$CCD/skills/daily-cost/config.json` | seta todos os `segments.*` = `true` e `proxy_port` |

## Multi-env (`.claude` + `.claude-pessoal` etc.)

Cada env roda seu próprio proxy em sua própria porta. O `proxy.pid`, `proxy.log` e `usage-state.json` ficam em `$CCD/skills/daily-cost/proxy/` — já isolados por env. Configure portas diferentes em cada `config.json["proxy_port"]` (ex.: 8765 e 8766). O `teardown` de um env mata só o daemon daquele env.
