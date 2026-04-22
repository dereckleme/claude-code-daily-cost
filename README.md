# claude-code-daily-cost

Skills para acompanhar o gasto do [Claude Code](https://claude.com/claude-code) no terminal, com **métricas inline direto na statusline** (hoje, semana, mês, sobra, reset, branch) e comando dedicado para ver o histórico em tabela.

![Statusline do Claude Code com métricas inline ativas](docs/statusline-inline.png)

## Principais comandos

### `/daily-cost-enable-metrics-inline`

Liga as métricas da statusline do Claude Code editando `~/.claude/skills/daily-cost/config.json`. A partir daí, o custo aparece **em tempo real** enquanto você trabalha — sem precisar rodar nenhum comando.

Na **primeira ativação**, a skill pergunta qual é a sua **cota mensal em USD** (default shipado é `100.00`, placeholder) e grava em `monthly_limit`. Nas próximas execuções, respeita o valor já configurado e não pergunta de novo.

```
/daily-cost-enable-metrics-inline              # liga tudo
/daily-cost-enable-metrics-inline today month  # só hoje e mês
/daily-cost-enable-metrics-inline hoje sobra   # aceita PT também
```

Segmentos disponíveis:

| Segmento | O que mostra |
|----------|--------------|
| `today` | `hoje $X` |
| `week` | `Nd úteis $X` |
| `month` | `mês $X/$LIMIT` |
| `remaining` | `sobra $X` dentro dos parênteses do mês |
| `reset` | data de reset dentro dos parênteses do mês |
| `branch` | `branch <nome> Xk tok · $X` (branch git do cwd + custo) |
| `limit` | `LIMITE X% · RESET Yh` (cota 5h em tempo real — requer proxy, ver abaixo) |

### `/daily-cost-disable-metrics-inline`

Desliga segmentos da statusline. Mesma sintaxe — sem argumentos desliga todos, ou passe os nomes pra desligar seletivamente.

```
/daily-cost-disable-metrics-inline             # desliga tudo
/daily-cost-disable-metrics-inline branch      # só esconde o segmento da branch
```

### `/daily-cost-enable-usage-proxy` — cota em tempo real

Sobe um proxy HTTP local em `127.0.0.1:8765` que fica entre o Claude Code e `api.anthropic.com`, captura os headers `anthropic-ratelimit-unified-*` que a API retorna a cada request e grava em `usage-state.json`. O segmento `limit` do statusline lê esse arquivo e mostra **porcentagem da cota 5h** + **tempo até o reset**, em tempo real.

**Transparência**: o proxy vê todo o tráfego, mas só grava uma allowlist de headers. Allowlist hardcoded em `proxy/proxy.py`. Escuta só em loopback.

**Instalação única**: adiciona `ANTHROPIC_BASE_URL` em `~/.claude/settings.json` e liga o segmento no `daily-cost/config.json`. Requer reiniciar o Claude Code.

```
/daily-cost-enable-usage-proxy           # default: porta 8765
/daily-cost-enable-usage-proxy porta=9999
/daily-cost-disable-usage-proxy          # reverte tudo
/daily-cost-disable-usage-proxy limpar   # reverte + apaga logs/state/pid
```

### `/daily-cost` (histórico em tabela)

Mostra gasto dos últimos N dias úteis + mês vs. limite, com gráfico ASCII.

```
/daily-cost        # últimos 5 dias úteis
/daily-cost 10     # últimos 10 dias úteis
```

Exemplo de saída:

```
  Claude Code — últimos 5 dias úteis  (custo em USD, tokens totais)
  ────────────────────────────────────────────────────────────────
  2026-04-15 Qua  $ 97.94  ████████████████████████████   36.56M tok  (733 msg)
  2026-04-16 Qui  $ 38.22  ███████████░░░░░░░░░░░░░░░░░   30.68M tok  (587 msg)
  2026-04-17 Sex  $ 12.66  ████░░░░░░░░░░░░░░░░░░░░░░░░   27.31M tok  (483 msg)
  2026-04-20 Seg  $ 41.10  ████████████░░░░░░░░░░░░░░░░   20.34M tok  (400 msg)
  2026-04-21 Ter  $ 65.76  ███████████████████░░░░░░░░░   19.60M tok  (316 msg)
  ────────────────────────────────────────────────────────────────
  TOTAL                     $255.68                                134.49M tok
```

## Instalação

```bash
git clone git@github.com:dereckleme/claude-code-daily-cost.git
cp -r claude-code-daily-cost/daily-cost ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-enable-metrics-inline ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-disable-metrics-inline ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-enable-usage-proxy ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-disable-usage-proxy ~/.claude/skills/
```

Pra statusline consumir o script inline, aponte `statusLine` no `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/skills/daily-cost/statusline.py"
  }
}
```

Reinicie o Claude Code. Depois rode `/daily-cost-enable-metrics-inline` e a statusline passa a mostrar o custo.

## Configuração

`~/.claude/skills/daily-cost/config.json`:

```json
{
  "segments": {
    "today": true,
    "week": true,
    "month": true,
    "remaining": true,
    "reset": true,
    "branch": true,
    "tpm_chart": true,
    "limit": false
  },
  "monthly_limit": 100.00,
  "plan_coefficient": 0.4419,
  "business_days": 5
}
```

- `segments` — o que aparece na statusline (controlado pelas skills `enable`/`disable-metrics-inline`)
- `monthly_limit` — teto mensal em USD (default shipado é `100.00`; a skill `enable-metrics-inline` te pergunta o valor real na primeira ativação)
- `plan_coefficient` — fator aplicado ao custo bruto (use `1.0` se você paga preço cheio da API)
- `business_days` — padrão quando `/daily-cost` é chamado sem argumento

## Skills incluídas

| Skill | Comando | O que faz |
|-------|---------|-----------|
| `daily-cost-enable-metrics-inline` | `/daily-cost-enable-metrics-inline` | **Liga** métricas na statusline |
| `daily-cost-disable-metrics-inline` | `/daily-cost-disable-metrics-inline` | **Desliga** métricas na statusline |
| `daily-cost-enable-usage-proxy` | `/daily-cost-enable-usage-proxy` | **Ativa** tracking de cota 5h em tempo real (via proxy local) |
| `daily-cost-disable-usage-proxy` | `/daily-cost-disable-usage-proxy` | **Desativa** o proxy e reverte settings.json |
| `daily-cost` | `/daily-cost [dias]` | Tabela com histórico de gasto |

## Requisitos

- Python 3
- Claude Code instalado com transcripts em `~/.claude/projects/`
