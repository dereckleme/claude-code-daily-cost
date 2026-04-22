---
name: daily-cost
description: Mostra gasto do Claude Code (hoje, últimos N dias úteis, mês) em tabela com gráfico de barras ASCII. Para ligar/desligar statusline + proxy de cota use daily-cost-analytics-enable / daily-cost-analytics-disable.
---

Execute o script e exiba a saída **exatamente como vem**, dentro de um bloco de código, sem reformatar nem comentar os números.

```bash
CCD="$(bash "$HOME/.claude/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
      || bash "$HOME/.claude-pessoal/skills/daily-cost/resolve-config-dir.sh" 2>/dev/null \
      || echo "$HOME/.claude")"
python3 "$CCD/skills/daily-cost/cost.py" "${1:-5}"
```

- O `CCD` resolve qual `~/.claude*` dir está ativo nesta sessão (via `$CLAUDE_CONFIG_DIR` → inspeção do processo claude → mtime dos transcripts). Nunca assuma `~/.claude` hardcoded.
- Se o usuário passar um argumento numérico (ex.: `/daily-cost 7`), use-o como número de dias. Senão, use 5.
- Não recalcule os valores — o script já aplica os preços de cada modelo.
- Depois da tabela, adicione **uma linha curta** destacando o dia de maior custo.
