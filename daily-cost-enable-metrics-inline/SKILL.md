---
name: daily-cost-enable-metrics-inline
description: Liga métricas do statusline do Claude Code (today, week, month, remaining, reset, branch, tpm, tpm_chart) editando ~/.claude/skills/daily-cost/config.json.
---

Liga segmentos do statusline inline. Config em `~/.claude/skills/daily-cost/config.json`, bloco `segments`:

- `today` — "hoje $X"
- `week` — "Nd úteis $X"
- `month` — "mês $X/$LIMIT"
- `remaining` — "sobra $X" dentro do parênteses do mês
- `reset` — data de reset dentro do parênteses do mês
- `branch` — "branch <nome> Xk tok · $X" (branch git do cwd + custo nessa branch)
- `tpm` — "TPM atual/média" (aparece na linha do gráfico)
- `tpm_chart` — gráfico mensal de barras + eixo de dias
- `limit` — "LIMITE X% · RESET Yh" (cota 5h em tempo real; **requer** `/daily-cost-enable-usage-proxy`)

## Passos

1. Leia `~/.claude/skills/daily-cost/config.json`.

2. **Garanta que `monthly_limit` reflete a cota real do usuário.** O default shipado é `100.00` — um placeholder. Se o valor atual for `100.00` (ou ≤ 0), **pergunte** ao usuário:

   > "Qual é a sua cota mensal do Claude Code em USD? (ex.: 200, 300). Aperte Enter pra manter 100."

   Aceite apenas número positivo. Se o usuário só der Enter ou disser "default"/"mantém", preserve 100. Grave o valor em `monthly_limit`.

   Se `monthly_limit` já estiver customizado (diferente de 100), **não pergunte** — respeite o que está lá.

3. Interprete o argumento do usuário pros segments:
   - **Sem argumento** ou palavras como "tudo", "all": ligue **todos** os segments (`today`, `week`, `month`, `remaining`, `reset`, `branch`, `tpm`, `tpm_chart` → `true`). **Não inclua `limit`** — ele depende do proxy e tem skill própria.
   - **Com nomes** (separados por espaço/vírgula, em PT ou EN — ex.: `hoje`, `semana`/`week`, `mes`/`month`, `sobra`/`remaining`, `reset`, `branch`, `tpm`, `grafico`/`chart`/`tpm_chart`, `limite`/`limit`): ligue só os nomeados.
   - Se o usuário pedir `limit`/`limite`: ligue no config.json **e avise** que sem o proxy o segmento fica vazio. Recomende rodar `/daily-cost-enable-usage-proxy`.

4. Edite o arquivo com a Edit tool (troque `false` por `true` nos campos correspondentes e ajuste `monthly_limit` se o usuário informou).

5. Rode pra confirmar e mostre a saída em bloco de código:

```bash
echo '{}' | python3 ~/.claude/skills/daily-cost/statusline.py
```

6. Resposta curta: uma frase dizendo quais segments ficaram ligados e qual cota mensal ficou configurada.

Não execute calibração de `plan_coefficient` nem mude `business_days` aqui — essa skill é só pros toggles de `segments` e pra confirmar `monthly_limit` na ativação.
