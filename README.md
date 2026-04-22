# claude-code-daily-cost

Skills para acompanhar o gasto do [Claude Code](https://claude.com/claude-code) no terminal, com **painel inline direto na statusline** (hoje, semana, mês, reset, branch, TPM, gráfico mensal, cota 5h em tempo real) e comando dedicado para ver o histórico em tabela.

![Statusline do Claude Code com o painel ativo](docs/statusline-inline.png)

## Comandos

### `/daily-cost-analytics-enable` — liga tudo

Liga **todos** os segmentos do statusline e sobe o proxy HTTP local que captura os headers `anthropic-ratelimit-*` da Anthropic pra mostrar a cota de 5h em tempo real.

- Edita `<CCD>/skills/daily-cost/config.json` setando todos os `segments.*` = `true`.
- Sobe o daemon em `127.0.0.1:8765` via `daily-cost/proxy/ensure-proxy.sh`.
- Adiciona `env.ANTHROPIC_BASE_URL=http://127.0.0.1:8765` em `<CCD>/settings.json`.
- **Requer reiniciar o Claude Code** (a env var só entra em vigor em sessões novas).

`<CCD>` = config dir ativo da sessão. Se você só tem `~/.claude`, é ele. Se tem múltiplos (`~/.claude`, `~/.claude-pessoal`, …), o próprio skill detecta qual está ativo via `$CLAUDE_CONFIG_DIR` env, inspeção do processo claude (`lsof`) ou mtime dos transcripts.

```
/daily-cost-analytics-enable             # default: porta 8765
/daily-cost-analytics-enable porta=9999
```

**Transparência do proxy**: vê todo o tráfego (é assim que um proxy funciona), mas só persiste uma allowlist de headers em `usage-state.json` (`anthropic-ratelimit-*`, `anthropic-organization-*`, `retry-after`, `anthropic-request-id`). Allowlist hardcoded em `proxy/proxy.py`. Escuta só em loopback.

Segmentos do statusline:

| Segmento | O que mostra |
|----------|--------------|
| `today` | `hoje $X` |
| `week` | `Nd úteis $X` |
| `month` | `mês $X` |
| `reset` | data de reset |
| `branch` | `branch <nome> Xk tok · $X` (branch git do cwd + custo) |
| `tpm` | TPM atual/média |
| `tpm_chart` | gráfico mensal de barras + eixo de dias |
| `limit` | `COTA FALTA Y% (X% usado) (reset em Zh)` — cota 5h em tempo real |

### `/daily-cost-analytics-disable` — desliga tudo

Inverso. Mata o proxy, remove `ANTHROPIC_BASE_URL` do `settings.json` (só se apontar pra `127.0.0.1:*`) e desliga todos os segments. Com tudo off, a statusline fica **completamente vazia**.

```
/daily-cost-analytics-disable            # preserva logs/state pra debug
/daily-cost-analytics-disable limpar     # apaga logs/state/pid também
```

### `/daily-cost` — histórico em tabela

Mostra gasto dos últimos N dias úteis + mês, com gráfico ASCII.

```
/daily-cost        # últimos 5 dias úteis
/daily-cost 10     # últimos 10 dias úteis
```

Exemplo:

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
cp -r claude-code-daily-cost/daily-cost-analytics-enable ~/.claude/skills/
cp -r claude-code-daily-cost/daily-cost-analytics-disable ~/.claude/skills/
```

> **Múltiplos config dirs** (`~/.claude`, `~/.claude-pessoal`, …)? Copie as skills pra cada dir que você usa. O projeto detecta o config dir ativo em runtime — não assume `~/.claude` em lugar nenhum.

Aponte a statusline pro script inline no `settings.json` do(s) dir(s) onde instalou:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/skills/daily-cost/statusline.py"
  }
}
```

(Troque `~/.claude` pelo dir correspondente em cada `settings.json`.) Reinicie o Claude Code. Depois rode `/daily-cost-analytics-enable` pra ligar o painel.

## Configuração

`<CCD>/skills/daily-cost/config.json`:

```json
{
  "segments": {
    "today": true,
    "week": true,
    "month": true,
    "reset": true,
    "branch": true,
    "tpm": true,
    "tpm_chart": true,
    "limit": true
  },
  "plan_coefficient": 0.4419,
  "business_days": 5
}
```

- `segments` — o que aparece na statusline (controlado pelas skills `analytics-enable`/`analytics-disable`)
- `plan_coefficient` — fator aplicado ao custo bruto (use `1.0` se você paga preço cheio da API)
- `business_days` — padrão quando `/daily-cost` é chamado sem argumento

## Skills incluídas

| Skill | Comando | O que faz |
|-------|---------|-----------|
| `daily-cost` | `/daily-cost [dias]` | Tabela com histórico de gasto |
| `daily-cost-analytics-enable` | `/daily-cost-analytics-enable` | **Liga** painel completo (statusline + proxy de cota) |
| `daily-cost-analytics-disable` | `/daily-cost-analytics-disable` | **Desliga** tudo e reverte `settings.json` |

## Requisitos

- Python 3
- Claude Code instalado com transcripts em `<CCD>/projects/` (detectado automaticamente)
- `lsof` e `ps` disponíveis (default no macOS/Linux) — usados pra resolver o config dir da sessão ativa quando existem múltiplos `~/.claude*`
