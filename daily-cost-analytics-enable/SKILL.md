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

2. **Determinar a porta** lendo `proxy_port` de `$CCD/skills/daily-cost/config.json` (default `8765`). Esse é apenas o ponto de partida — o `ensure-proxy.sh` avança automaticamente para a próxima porta livre e persiste o valor resolvido em `config.json` e `settings.json`. Se o argumento `porta=<N>` foi passado, salve-o em `config.json["proxy_port"]` antes de continuar.

3. **Subir proxy**: `bash "$CCD/skills/daily-cost/proxy/ensure-proxy.sh"`. O script lê `config.json` para a porta inicial, auto-avança se ocupada e atualiza ambos os arquivos com a porta resolvida.

4. **Health check**: `curl -s http://127.0.0.1:<porta>/_usage_proxy_health` deve retornar `{"ok": true, "state": {...}}`.

5. **Verificar ANTHROPIC_BASE_URL** em `$CCD/settings.json` — o `ensure-proxy.sh` já atualizou automaticamente. Apenas confirme que aponta para `http://127.0.0.1:<porta_resolvida>`. Se ainda apontar para outro lugar (Bedrock/Vertex/outro proxy externo que **não** seja `http://127.0.0.1:*`), **pergunte** antes de sobrescrever.

5.5. **Verificar e inserir `statusLine`** em `$CCD/settings.json` — se a chave `statusLine` não existir, adicione-a apontando para o script da sessão ativa:
   ```python
   import json, os
   settings_path = os.path.join(CCD, "settings.json")
   with open(settings_path, "r") as f:
       settings = json.load(f)
   if "statusLine" not in settings:
       settings["statusLine"] = {
           "type": "command",
           "command": f"python3 {CCD}/skills/daily-cost/statusline.py"
       }
       with open(settings_path, "w") as f:
           json.dump(settings, f, indent=4)
       print("statusLine adicionado ao settings.json")
   else:
       print("statusLine já configurado:", settings["statusLine"])
   ```
   Se `statusLine` já existir e apontar para **outro** script (não o `statusline.py` do daily-cost), **não sobrescreva** — avise o usuário e pergunte se quer substituir.

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
| `$CCD/skills/daily-cost/proxy/proxy.session` | criado (PID do Claude Code desta sessão) |
| `$CCD/skills/daily-cost/proxy/proxy_YYYYMMDDTHHMMSS.log` | criado (log da sessão) |
| `$CCD/skills/daily-cost/proxy/proxy.log` | symlink → log da sessão atual |
| `$CCD/skills/daily-cost/proxy/usage-state.json` | criado/atualizado a cada request |
| `$CCD/settings.json` | adiciona `env.ANTHROPIC_BASE_URL` e `statusLine` (se ausente) |
| `$CCD/skills/daily-cost/config.json` | seta todos os `segments.*` = `true` e `proxy_port` |

## Proxy por instância do Claude Code

Cada vez que `ensure-proxy.sh` é chamado, o script detecta o PID do processo Claude Code pai (percorrendo a árvore de processos). Esse PID é gravado em `proxy.session`.

- **Mesma sessão**: se o proxy já está no ar e `proxy.session` bate com o Claude Code atual → reutiliza (idempotente).
- **Nova sessão** (Claude Code foi reiniciado ou é outra janela): o proxy antigo é encerrado e um novo é iniciado com um arquivo de log dedicado.

Logs são nomeados com timestamp: `proxy_YYYYMMDDTHHMMSS.log`. O symlink `proxy.log` aponta sempre para o log da sessão atual.

## Multi-env (`.claude` + `.claude-pessoal` etc.)

Cada env roda seu próprio proxy em sua própria porta, com arquivos (`proxy.pid`, `proxy.session`, `proxy_*.log`, `usage-state.json`) isolados em `$CCD/skills/daily-cost/proxy/`. Configure portas diferentes em cada `config.json["proxy_port"]` (ex.: 8765 e 8766). O `teardown` de um env mata só o daemon daquele env.
