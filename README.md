# claude-code-daily-cost

Skills para acompanhar o gasto do [Claude Code](https://claude.com/claude-code) direto no terminal.

Mostra quanto você gastou hoje, nos últimos N dias úteis e no mês (vs. limite configurado), com gráfico de barras ASCII. Inclui também toggles para exibir métricas inline na statusline.

## Skills incluídas

| Skill | Comando | O que faz |
|-------|---------|-----------|
| `daily-cost` | `/daily-cost [dias]` | Tabela com gasto de hoje, últimos N dias úteis e mês vs. limite |
| `daily-cost-enable-metrics-inline` | `/daily-cost-enable-metrics-inline` | Liga métricas na statusline (today, week, month, remaining, reset) |
| `daily-cost-disable-metrics-inline` | `/daily-cost-disable-metrics-inline` | Desliga as métricas inline |

## Instalação

Copie cada pasta de skill para `~/.claude/skills/`:

```bash
git clone git@github.com:dereckleme/claude-code-daily-cost.git
cp -r claude-code-daily-cost/daily-cost ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-enable-metrics-inline ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-disable-metrics-inline ~/.claude/skills/
```

Reinicie o Claude Code e os comandos `/daily-cost`, `/daily-cost-enable-metrics-inline` e `/daily-cost-disable-metrics-inline` estarão disponíveis.

## Configuração

Edite `~/.claude/skills/daily-cost/config.json`:

```json
{
  "segments": {
    "today": true,
    "week": true,
    "month": true,
    "remaining": true,
    "reset": true,
    "branch": true,
    "tpm_chart": true
  },
  "monthly_limit": 300.00,
  "plan_coefficient": 0.4419,
  "business_days": 5
}
```

- `monthly_limit` — seu teto mensal em USD
- `plan_coefficient` — fator aplicado ao custo bruto (use `1.0` se pagar preço cheio da API)
- `business_days` — padrão de dias úteis usado quando o comando é chamado sem argumento
- `segments` — quais métricas aparecem na statusline quando habilitadas

## Uso

```bash
/daily-cost        # últimos 5 dias úteis + mês
/daily-cost 10     # últimos 10 dias úteis
```

## Requisitos

- Python 3
- Claude Code instalado com transcripts em `~/.claude/projects/`
