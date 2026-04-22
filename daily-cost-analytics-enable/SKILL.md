---
name: daily-cost-analytics-enable
description: Liga o painel completo do daily-cost — todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit) + proxy HTTP local que captura headers anthropic-ratelimit-* pra mostrar cota de 5h em tempo real. Edita settings.json do config dir ativo e requer reiniciar o Claude Code.
---

Skill única pra ligar **tudo** do daily-cost de uma vez: segmentos do statusline + proxy de tracking de cota.

## O que esta skill faz

1. Liga todos os segmentos em `$CCD/skills/daily-cost/config.json`.
2. Sobe o proxy HTTP local (porta 8765 por padrão) via `$CCD/skills/daily-cost/proxy/ensure-proxy.sh`. O proxy captura só os headers `anthropic-ratelimit-*` e `anthropic-organization-*` — body de request/response nunca é lido nem persistido.
3. Insere `env.ANTHROPIC_BASE_URL=http://127.0.0.1:<porta>/_env_<LABEL>` em `$CCD/settings.json`. O prefixo `/_env_<LABEL>` (ex.: `/_env_default`, `/_env_pessoal`) identifica qual `.claude*` está chamando, pro proxy separar o `usage-state-<LABEL>.json` por env quando múltiplas instâncias compartilham o mesmo proxy.
4. Avisa que é preciso reiniciar o Claude Code pra a env var entrar em vigor.

`$CCD` = config dir ativo desta sessão (`~/.claude`, `~/.claude-pessoal`, …). Ver passo 0 abaixo.

## Transparência

- **O que o proxy vê**: 100% do tráfego Claude Code → Anthropic (mensagens, tool calls, bearer). Inevitável pra qualquer proxy.
- **O que persiste em disco**: só `usage-state.json` com os headers na allowlist (`anthropic-ratelimit-*`, `anthropic-organization-*`, `retry-after`, `anthropic-request-id`). Allowlist hardcoded em `proxy/proxy.py` (`CAPTURED_PREFIXES`, `CAPTURED_EXACT`).
- **Rede**: proxy escuta só em 127.0.0.1.

## Passos que o Claude vai executar

0. **Resolver config dir da sessão ativa e derivar o LABEL** — rode o helper e guarde em `CCD`. Todos os passos seguintes usam `$CCD`, **nunca** `~/.claude` hardcoded:
   ```bash
   CCD="$(bash "$HOME/.claude/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || bash "$HOME/.claude-pessoal/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || echo "$HOME/.claude")"
   LABEL="$(python3 "$CCD/skills/daily-cost/session_dir.py" label 2>/dev/null || echo default)"
   echo "config dir: $CCD  label: $LABEL"
   ```
   Se o usuário tem múltiplos `~/.claude*` dirs, o helper detecta qual está ativo via `$CLAUDE_CONFIG_DIR` env, inspeção do processo claude (lsof) ou mtime dos transcripts. `LABEL` vira `default` pra `~/.claude`, `pessoal` pra `~/.claude-pessoal` etc. — é o rótulo que o proxy usa pra separar o state por env.

1. **Ligar segmentos** editando `$CCD/skills/daily-cost/config.json` → bloco `segments` com todos os campos `true` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit`).

2. **Subir proxy**: `bash "$CCD/skills/daily-cost/proxy/ensure-proxy.sh"`. Se a porta 8765 estiver ocupada, o script aborta — escolha outra via `CLAUDE_USAGE_PROXY_PORT=<porta> bash ensure-proxy.sh <porta>`.

3. **Health check**: `curl -s http://127.0.0.1:<porta>/_usage_proxy_health` deve retornar `{"ok": true, "state": {...}}`.

4. **Inserir ANTHROPIC_BASE_URL** em `$CCD/settings.json` no bloco `env`, com o sufixo `/_env_<LABEL>`:
   ```json
   { "env": { "ANTHROPIC_BASE_URL": "http://127.0.0.1:8765/_env_default" } }
   ```
   (Para `~/.claude-pessoal` seria `/_env_pessoal`, etc.) O sufixo permite que um único proxy atenda múltiplas instâncias do Claude Code separando o `usage-state-<LABEL>.json` por env. Se já existia apontando pra outro lugar (Bedrock/Vertex/outro proxy externo que **não** seja `http://127.0.0.1:*`), **pergunte** antes de sobrescrever.

5. **Avisar**: "⚠️ Reinicie Claude Code pra ativar o tracking. A env var só entra em vigor em sessões novas."

6. Rodar `echo '{}' | python3 "$CCD/skills/daily-cost/statusline.py"` e mostrar a saída atual em bloco de código.

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
| `$CCD/skills/daily-cost/proxy/proxy.pid` | criado (só pelo primeiro env a subir o daemon) |
| `$CCD/skills/daily-cost/proxy/proxy.log` | criado (append) |
| `$CCD/skills/daily-cost/proxy/usage-state-<LABEL>.json` | criado/atualizado a cada request do env |
| `$CCD/settings.json` | adiciona `env.ANTHROPIC_BASE_URL=http://127.0.0.1:<porta>/_env_<LABEL>` |
| `$CCD/skills/daily-cost/config.json` | seta todos os `segments.*` = `true` |

## Multi-env (`.claude` + `.claude-pessoal` etc.)

Um único proxy na porta 8765 atende todas as instâncias — quem chega primeiro sobe o daemon, as outras reusam. Cada env grava em `usage-state-<LABEL>.json` separado, então a statusline de cada instância lê só os headers do seu próprio tráfego.

O `teardown` de um env mata o daemon compartilhado. Se você ainda tem outra instância ativa, rode `/daily-cost-analytics-enable` nela pra subir de novo.
