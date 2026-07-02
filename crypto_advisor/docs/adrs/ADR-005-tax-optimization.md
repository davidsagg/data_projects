# ADR-005: Estratégia de Tax Optimization (isenção R$35k/mês — IN RFB 2.312/2026)

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

A Instrução Normativa RFB 2.312/2026 mantém a isenção de IR sobre ganhos de capital em criptoativos para vendas totais **por exchange** inferiores a **R$35.000 por mês**. O limite é individual por corretora, não consolidado.

Com uma carteira de R$5.000 crescendo com aportes mensais e estratégia de swing trading, há risco real de ultrapassar o limite em meses de alta volatilidade/oportunidades. O custo de um erro é 15–22,5% de IR sobre o ganho de capital.

**Objetivo:** Maximizar a renda mensal em BRL mantendo-se sistematicamente abaixo do limite de isenção.

---

## Decisão

Implementar o **Tax Optimizer Module** como componente de primeira classe, integrado ao fluxo de recomendação do Claude, com quatro zonas de operação e três estratégias automáticas.

---

## Zonas de Operação

```
R$0                R$28k          R$33k       R$35k
│──────────────────│──────────────│───────────│──────────
│      SAFE        │   WARNING    │  CRITICAL │  BLOCKED
│  opera normal    │ priorizar    │ só loss   │ sem vendas
│                  │ loss harvest │ harvesting│ este mês
```

| Zona       | Faixa BRL vendido   | Ação do sistema                                              |
|------------|---------------------|--------------------------------------------------------------|
| SAFE       | < R$28.000          | Recomendações normais; Claude inclui impacto fiscal no output |
| WARNING    | R$28k – R$33k       | Claude prioriza loss harvesting e ativos com gain menor; alerta Telegram |
| CRITICAL   | R$33k – R$35k       | Apenas operações de loss harvesting são aprovadas; bloqueia BUY com lucro |
| BLOCKED    | ≥ R$35.000          | Nenhuma venda aprovada neste mês; Claude analisa compras e mantém posições |

---

## Estratégias Implementadas

### 1. Rastreamento mensal
- Toda venda registrada em `trades` atualiza `tax_tracker` automaticamente via trigger/repositório
- Cálculo: `total_sold_brl` = soma de `total_brl` onde `side='sell'` no mês/ano/exchange

### 2. Loss Harvesting
- Identificar posições com prejuízo não realizado (custo médio > preço atual)
- Sugerir venda para realizar a perda (reduz base tributável futura se houver ganhos compensáveis)
- A perda realizada não conta para o limite de isenção — apenas o volume vendido em BRL conta

### 3. Income Strategy (distribuição de lucros)
- Em meses com limite folgado, sugerir realização parcial de lucros para gerar renda em BRL
- Priorizar ativos com maior % de ganho e maior liquidez
- Manter pelo menos R$2.000 de margem abaixo do limite (meta: vender até R$33.000/mês)

---

## Integração com Claude

O contexto fiscal é sempre incluído no prompt de recomendação:

```
TAX STATUS (Mercado Bitcoin — Maio/2026):
  Vendas acumuladas: R$12.400,00 / R$35.000,00 (35%)
  Zona: SAFE
  Margem disponível: R$22.600,00
  Instrução: operar normalmente; incluir impacto fiscal em cada recomendação de venda
```

---

## Consequências

- **Positivas:** Economia potencial de 15–22,5% em ganhos realizados; rastreamento automatizado elimina risco de erro manual; integrado ao fluxo já existente
- **Negativas:** Lógica fiscal pode ser conservadora em relação a oportunidades de mercado (trade-off explícito)
- **Mitigações:** O usuário pode sobrepor o status via Streamlit UI; sistema nunca executa automaticamente (human-in-the-loop garante controle)
- **Disclaimer:** Esta implementação é uma ferramenta auxiliar de planejamento financeiro. Consulte um contador especializado em criptoativos para decisões fiscais definitivas.

---

## Referências

- IN RFB 2.312/2026 (sucessora da IN 1.888/2019)
- Solução de Consulta COSIT 214/2021 — base de cálculo por exchange
