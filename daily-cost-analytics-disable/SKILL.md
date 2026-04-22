---
name: daily-cost-analytics-disable
description: Desliga o painel completo do daily-cost — mata o proxy HTTP local, remove ANTHROPIC_BASE_URL do settings.json do config dir ativo e desliga todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit).
---

Inverso de `/daily-cost-analytics-enable`. Deixa o Claude Code falando direto com `api.anthropic.com` e oculta todo o painel do statusline.

## Passos que o Claude vai executar

0. **Resolver config dir da sessão ativa** — rode o helper e guarde em `CCD`. Todos os passos seguintes usam `$CCD`, **nunca** `~/.claude` hardcoded:
   ```bash
   CCD="$(bash "$HOME/.claude/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || bash "$HOME/.claude-pessoal/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
         || echo "$HOME/.claude")"
   echo "config dir: $CCD"
   ```

1. **Desligar segmentos** editando `$CCD/skills/daily-cost/config.json`:
   - Setar todos os campos do bloco `segments` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit`) = `false`.
   - Com todos desligados, a statusline fica completamente vazia (nem o prefixo `$$ DAILY COST $$` é impresso).

2. **Matar o proxy**:
   ```bash
   bash "$CCD/skills/daily-cost/proxy/teardown.sh"
   ```

3. **Remover `env.ANTHROPIC_BASE_URL`** de `$CCD/settings.json` (último passo — altera a conexão somente após todo o resto estar desligado):
   - Se o valor apontar pra `http://127.0.0.1:*` (qualquer porta local), remova essa chave.
   - Se `env` ficar vazio depois, remova o bloco `env` inteiro.
   - Se apontar pra outra coisa (Bedrock, Vertex, outro proxy externo), **não mexer** e avisar o usuário que o valor não é do daily-cost.

4. **Avisar**: "Reinicie Claude Code pra voltar a falar direto com api.anthropic.com. Até reiniciar, a sessão atual continua usando a URL anterior (proxy já parado) e vai falhar nos próximos requests."

5. **Opcional — limpar artefatos**: se o usuário passar `limpar` como argumento, remover também:
   - `$CCD/skills/daily-cost/proxy/proxy.pid`
   - `$CCD/skills/daily-cost/proxy/proxy.session`
   - `$CCD/skills/daily-cost/proxy/proxy.log` (symlink)
   - `$CCD/skills/daily-cost/proxy/proxy_*.log` (todos os logs de sessões anteriores)
   - `$CCD/skills/daily-cost/proxy/usage-state.json`

## Argumentos aceitos

- Sem argumento: desativa mantendo logs e state pra consulta.
- `limpar`: desativa e apaga logs/state/pid/session.

## Resposta final

Uma frase curta dizendo que os segmentos foram desligados, o proxy foi parado e `settings.json` foi revertido. Reforçar o aviso de reiniciar o Claude Code.
