---
name: daily-cost-disable-metrics-inline
description: Desliga métricas do statusline do Claude Code (today, week, month, remaining, reset, branch, tpm, tpm_chart) editando ~/.claude/skills/daily-cost/config.json.
---

Desliga segmentos do statusline inline. Config em `~/.claude/skills/daily-cost/config.json`, bloco `segments`:

- `today` — "hoje $X"
- `week` — "Nd úteis $X"
- `month` — "mês $X/$LIMIT"
- `remaining` — "sobra $X" dentro do parênteses do mês
- `reset` — data de reset dentro do parênteses do mês
- `branch` — "branch <nome> Xk tok · $X" (branch git do cwd + custo nessa branch)
- `tpm` — "TPM atual/média" (aparece na linha do gráfico)
- `tpm_chart` — gráfico mensal de barras + eixo de dias
- `limit` — "LIMITE X% · RESET Yh" (cota 5h em tempo real)

Quando **todos** os segments estão desligados, a statusline fica **completamente vazia** (nem o prefixo `$$ DAILY COST $$` é impresso).

## Passos

1. Leia `~/.claude/skills/daily-cost/config.json`.
2. Interprete o argumento do usuário:
   - **Sem argumento** ou palavras como "tudo", "all": desligue **todos** os segments (`today`, `week`, `month`, `remaining`, `reset`, `branch`, `tpm`, `tpm_chart`, `limit` → `false`).
   - **Com nomes** (separados por espaço/vírgula, em PT ou EN — ex.: `hoje`, `semana`/`week`, `mes`/`month`, `sobra`/`remaining`, `reset`, `branch`, `tpm`, `grafico`/`chart`/`tpm_chart`, `limite`/`limit`): desligue só os nomeados.
   - Desligar `limit` aqui **não mata o proxy** — só esconde o segmento. Pra parar o proxy também, use `/daily-cost-disable-usage-proxy`.
3. Edite o arquivo com a Edit tool (troque `true` por `false` nos campos correspondentes). Se algum segment não existir no bloco, adicione com `false`.
4. Rode pra confirmar e mostre a saída em bloco de código:

```bash
echo '{}' | python3 ~/.claude/skills/daily-cost/statusline.py
```

5. Resposta curta: uma frase dizendo quais segments ficaram desligados.

Não execute calibração de coeficiente nem mude `monthly_limit`/`business_days` aqui — essa skill é só pros toggles de `segments`.
