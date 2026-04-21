---
name: daily-cost-enable-metrics-inline
description: Liga métricas do statusline do Claude Code (today, week, month, remaining, reset) editando ~/.claude/skills/daily-cost/config.json.
---

Liga segmentos do statusline inline. Config em `~/.claude/skills/daily-cost/config.json`, bloco `segments`:

- `today` — "hoje $X"
- `week` — "Nd úteis $X"
- `month` — "mês $X/$LIMIT"
- `remaining` — "sobra $X" dentro do parênteses do mês
- `reset` — data de reset dentro do parênteses do mês
- `branch` — "branch <nome> Xk tok · $X" (branch git do cwd + custo nessa branch)

## Passos

1. Leia `~/.claude/skills/daily-cost/config.json`.
2. Interprete o argumento do usuário:
   - **Sem argumento** ou palavras como "tudo", "all": ligue **todos** os segments (`today`, `week`, `month`, `remaining`, `reset`, `branch` → `true`).
   - **Com nomes** (separados por espaço/vírgula, em PT ou EN — ex.: `hoje`, `semana`/`week`, `mes`/`month`, `sobra`/`remaining`, `reset`, `branch`): ligue só os nomeados.
3. Edite o arquivo com a Edit tool (troque `false` por `true` nos campos correspondentes).
4. Rode pra confirmar e mostre a saída em bloco de código:

```bash
echo '{}' | python3 ~/.claude/skills/daily-cost/statusline.py
```

5. Resposta curta: uma frase dizendo quais segments ficaram ligados.

Não execute calibração de coeficiente nem mude `monthly_limit`/`business_days` aqui — essa skill é só pros toggles de `segments`.
