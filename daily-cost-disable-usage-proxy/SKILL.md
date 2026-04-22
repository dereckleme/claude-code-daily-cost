---
name: daily-cost-disable-usage-proxy
description: Desativa o tracking de cota em tempo real. Mata o proxy, remove ANTHROPIC_BASE_URL do ~/.claude/settings.json e desliga o segmento LIMITE do statusline.
---

## Passos que o Claude vai executar

1. **Matar o proxy** rodando:
   ```bash
   bash ~/.claude/skills/daily-cost-enable-usage-proxy/proxy/teardown.sh
   ```

2. **Remover `ANTHROPIC_BASE_URL`** de `~/.claude/settings.json`:
   - Ler o arquivo.
   - Se `env.ANTHROPIC_BASE_URL` apontar pra `http://127.0.0.1:*` (qualquer porta local), remover esse campo.
   - Se `env` ficar vazio depois da remoção, remover o bloco `env` inteiro.
   - Se apontar pra outra coisa (ex: Bedrock, Vertex), **não mexer** e avisar o usuário que o valor não é nosso.

3. **Desligar o segmento `LIMITE`** editando `~/.claude/skills/daily-cost/config.json`: setar `segments.limit = false`.

4. **Avisar o usuário**: "Reinicie Claude Code pra voltar a falar direto com api.anthropic.com. Até reiniciar, a sessão atual continua usando o proxy (que já morreu) e vai falhar nos próximos requests."

5. **Opcional — limpar artefatos do skill**: se o usuário passar `limpar` como argumento, remover também:
   - `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/proxy.pid`
   - `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/proxy.log`
   - `~/.claude/skills/daily-cost-enable-usage-proxy/proxy/usage-state.json`

   Sem o argumento, preservar os arquivos (podem ser úteis pra debug).

## Argumentos aceitos

- Sem argumento: desativa mantendo logs e state pra consulta.
- `limpar`: desativa e apaga logs/state/pid.

## Resposta final

Uma frase curta dizendo que o proxy foi desativado, settings.json foi revertido e o segmento LIMITE está desligado. Reforçar o aviso de reiniciar Claude Code.
