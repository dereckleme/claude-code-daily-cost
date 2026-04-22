---
name: daily-cost-enable-usage-proxy
description: Ativa rastreio em tempo real da cota (5h/semanal) do Claude Code via proxy HTTP local. Sobe daemon em 127.0.0.1:8765, adiciona ANTHROPIC_BASE_URL em ~/.claude/settings.json e liga o segmento LIMITE no statusline do daily-cost. Requer reiniciar o Claude Code.
---

## O que esta skill faz

Claude Code não persiste informação de cota em nenhum lugar local — o banner "X% of your session limit" vem dos headers `anthropic-ratelimit-unified-*` que a API retorna a cada request e são descartados logo depois. Esta skill sobe um proxy HTTP local que fica entre o Claude Code e `api.anthropic.com`, captura apenas esses headers e grava em `proxy/usage-state.json`. O statusline do `daily-cost` lê esse arquivo e mostra porcentagem + reset em tempo real.

## Transparência (leia antes de ativar)

**O que o proxy vê**: 100% do tráfego Claude Code → Anthropic (mensagens, tool calls, bearer OAuth). É inevitável — é assim que um proxy funciona.

**O que o proxy guarda**: apenas os headers na allowlist abaixo, em `proxy/usage-state.json`:
- `anthropic-ratelimit-*` (prefixo completo)
- `anthropic-organization-*` (prefixo completo)
- `anthropic-request-id`
- `retry-after`

**O que o proxy nunca guarda**: body de request, body de response, bearer token, conteúdo das mensagens. A allowlist está hardcoded em `proxy/proxy.py` (constantes `CAPTURED_PREFIXES` e `CAPTURED_EXACT`).

**Rede**: o proxy escuta só em `127.0.0.1` (loopback). Não aceita conexão remota.

## Passos que o Claude vai executar

1. **Subir o proxy** rodando `proxy/ensure-proxy.sh`. Se a porta 8765 estiver ocupada, o script aborta e você escolhe outra via `CLAUDE_USAGE_PROXY_PORT=<porta>`.

2. **Testar health** batendo em `http://127.0.0.1:8765/_usage_proxy_health`. Deve retornar `{"ok": true, "state": {...}}`.

3. **Editar `~/.claude/settings.json`** adicionando (ou atualizando) o bloco `env.ANTHROPIC_BASE_URL`. Cercar com marcadores pra remoção limpa depois:

   ```json
   {
     "env": {
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8765"
     }
   }
   ```

   Se o usuário já tinha outros campos em `env`, preservar. Se já tinha `ANTHROPIC_BASE_URL` apontando pra outro lugar, **pergunte** antes de sobrescrever.

4. **Ligar o segmento `LIMITE` no statusline** editando `~/.claude/skills/daily-cost/config.json` para incluir `"limit": true` no bloco `segments`. Se o arquivo não tiver esse campo, adicione.

5. **Avisar o usuário**: "⚠️ Reinicie Claude Code pra ativar o tracking. O ANTHROPIC_BASE_URL só entra em vigor em sessões novas."

6. **Mostrar status final**: porta em uso, PID do daemon, caminho do state file.

## Argumentos aceitos

- Sem argumento (default): segue o fluxo acima com porta 8765.
- `porta=<N>`: usa porta customizada (ex.: `/daily-cost-enable-usage-proxy porta=9999`).

## Ciclo de vida

- **Pós-instalação**: daemon sobrevive fechar o terminal (via `nohup` + `disown`).
- **Pós-reboot**: daemon morre. Rode `/daily-cost-enable-usage-proxy` de novo — é idempotente, detecta que está morto e ressuscita.
- **Desinstalação**: use `/daily-cost-disable-usage-proxy`. Mata o daemon, reverte settings.json, desliga o segmento.

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/proxy.pid` | criado |
| `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/proxy.log` | criado (append) |
| `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/usage-state.json` | criado (atualiza a cada request) |
| `~/.claude/settings.json` | adiciona `env.ANTHROPIC_BASE_URL` |
| `~/.claude/skills/daily-cost/config.json` | seta `segments.limit = true` |

Nenhum outro arquivo do sistema é modificado. Sem `launchd`, sem `.zshrc`, sem `LaunchAgents`.
