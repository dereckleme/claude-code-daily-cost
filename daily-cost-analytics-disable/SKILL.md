---
name: daily-cost-analytics-disable
description: Desliga o painel completo do daily-cost — mata o proxy HTTP local, remove ANTHROPIC_BASE_URL de ~/.claude/settings.json e desliga todos os segmentos do statusline (today, week, month, reset, branch, tpm, tpm_chart, limit).
---

Inverso de `/daily-cost-analytics-enable`. Deixa o Claude Code falando direto com `api.anthropic.com` e oculta todo o painel do statusline.

## Passos que o Claude vai executar

1. **Matar o proxy**:
   ```bash
   bash ~/.claude/skills/daily-cost/proxy/teardown.sh
   ```

2. **Remover `env.ANTHROPIC_BASE_URL`** de `~/.claude/settings.json`:
   - Se o valor apontar pra `http://127.0.0.1:*` (qualquer porta local), remova essa chave.
   - Se `env` ficar vazio depois, remova o bloco `env` inteiro.
   - Se apontar pra outra coisa (Bedrock, Vertex, outro proxy externo), **não mexer** e avisar o usuário que o valor não é do daily-cost.

3. **Desligar segmentos** editando `~/.claude/skills/daily-cost/config.json`:
   - Setar todos os campos do bloco `segments` (`today`, `week`, `month`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit`) = `false`.
   - Com todos desligados, a statusline fica completamente vazia (nem o prefixo `$$ DAILY COST $$` é impresso).

4. **Avisar**: "Reinicie Claude Code pra voltar a falar direto com api.anthropic.com. Até reiniciar, a sessão atual continua usando o proxy (já morto) e vai falhar nos próximos requests."

5. **Opcional — limpar artefatos**: se o usuário passar `limpar` como argumento, remover também:
   - `~/.claude/skills/daily-cost/proxy/proxy.pid`
   - `~/.claude/skills/daily-cost/proxy/proxy.log`
   - `~/.claude/skills/daily-cost/proxy/usage-state.json`

## Argumentos aceitos

- Sem argumento: desativa mantendo logs e state pra consulta.
- `limpar`: desativa e apaga logs/state/pid.

## Resposta final

Uma frase curta dizendo que o proxy foi parado, `settings.json` foi revertido e todos os segmentos do statusline estão desligados. Reforçar o aviso de reiniciar o Claude Code.
