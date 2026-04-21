---
name: daily-cost
description: Mostra gasto do Claude Code (hoje, últimos N dias úteis, mês vs. limite) em tabela com gráfico de barras ASCII. Para toggles inline do statusline use daily-cost-enable-metrics-inline / daily-cost-disable-metrics-inline.
---

Execute o script e exiba a saída **exatamente como vem**, dentro de um bloco de código, sem reformatar nem comentar os números.

```bash
python3 ~/.claude/skills/daily-cost/cost.py "${1:-5}"
```

- Se o usuário passar um argumento numérico (ex.: `/daily-cost 7`), use-o como número de dias. Senão, use 5.
- Não recalcule os valores — o script já aplica os preços de cada modelo.
- Depois da tabela, adicione **uma linha curta** destacando o dia de maior custo.
