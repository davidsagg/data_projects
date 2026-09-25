# VeloDNA — Design Benchmark & UI Reference

> Documento de referência para o Claude Code construir a interface do VeloDNA.
> **Versão 2.0** · Abril 2026 · Calibrado para desktop-first + estética calma

---

## 1. Decisões de Design Fechadas

Estas decisões foram tomadas e não devem ser revisitadas durante a implementação.

| Decisão | Escolha | Implicação |
|---|---|---|
| **Contexto de uso** | Desktop-first, análise pós-treino | Canvas de 1440px. Mobile é secundário e responsivo, nunca prioritário. |
| **Estética** | Calma e espaçosa (Oura, Whoop) | Menos elementos por tela, tipografia maior, paleta dessaturada, muito espaço negativo. |
| **Problema #1 a resolver** | "Não vejo minha semana de forma clara" | A tela `/week` é a tela principal, não o dashboard genérico. |
| **Problema #2 a resolver** | "Saúde e treino em análises separadas" | Timeline unificada é o componente-assinatura do produto. |

### 1.1 A tensão central — e como resolvê-la

Análise profunda em desktop pede densidade. Estética calma pede respiro.
A resolução não é escolher um lado, é usar o espaço do desktop **para dar respiro à densidade**:

- Um monitor de 1440px comporta 8 métricas com muito espaço entre elas — no mobile, as mesmas 8 métricas viram uma parede
- Densidade vem da **quantidade de informação disponível**, não da quantidade de pixels ocupados
- Cada tela responde a **uma pergunta**. Se responde a duas, são duas telas.

**Regra prática:** máximo de 5 blocos visuais por tela. Se precisar de um sexto, ele
pertence a outra tela ou a um drill-down.

---

## 2. O Componente-Assinatura: Timeline Unificada

Nenhum concorrente faz isso. É o diferencial visual e funcional do VeloDNA.

```
SEMANA  14 – 20 abril                      ◀  anterior      próxima  ▶


                    TREINO
        TSS    ┃
        250    ┃         ▇▇▇                    ▇▇▇▇
        200    ┃         ▇▇▇         ▇▇▇        ▇▇▇▇
        150    ┃  ▇▇▇    ▇▇▇         ▇▇▇        ▇▇▇▇
        100    ┃  ▇▇▇    ▇▇▇   ▇▇    ▇▇▇        ▇▇▇▇   ▇▇
               ┃
               ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    SAÚDE
        HRV    ┃   ╭─────╮                     ╭───╮
        50ms   ┃  ╭╯      ╰──╮        ╭────────╯    ╰─╮
        40ms   ┃ ╭╯          ╰───────╯               ╰──
               ┃
        sono   ┃  ▁▁▁▁  ▁▁▁▁▁ ▁▁▁   ▁▁▁▁▁▁  ▁▁▁   ▁▁▁▁▁
               ┃  7h12   8h04  6h30   7h48   6h55   8h20
               ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                 SEG    TER    QUA    QUI    SEX    SÁB   DOM
```

**Por que funciona:** o eixo X é compartilhado. Você vê imediatamente que a noite
de 6h30 na quarta antecedeu o treino fraco de quinta, ou que o HRV caiu após o
bloco de terça. Nenhuma plataforma existente coloca esses dois eixos na mesma
linha do tempo.

**Interações:**
- Hover em qualquer dia → destaca a coluna inteira nos dois painéis
- Click no dia → drawer lateral com detalhe do treino + saúde daquele dia
- Sem tooltips flutuantes — os valores aparecem fixos no rodapé de cada painel

---

## 3. Análise dos Concorrentes

| Plataforma | Acerta | Erra | O que roubar |
|---|---|---|---|
| **Oura** | Calma visual, tipografia, espaçamento generoso | Zero análise de potência | Escala tipográfica, espaço negativo |
| **Whoop** | Um número dominante, cor semântica, storytelling | Superficial para treino estruturado | Hierarquia do "recovery score" |
| **Intervals.icu** | Densidade, PMC completo, customização | Visual datado, sem hierarquia | Lógica do PMC (não o visual) |
| **TrainingPeaks** | Análise mais completa do mercado | Interface pesada, muitos cliques | Profundidade métrica |
| **Golden Cheetah** | Profundidade analítica sem igual | UI de desktop dos anos 2000 | Modelos matemáticos |
| **Garmin Connect** | Dados de saúde ricos | Navegação confusa, treino fraco | Riqueza dos dados de sono/HRV |
| **Linear / Vercel** | Dark mode, hierarquia, densidade sem ruído | — | Padrões de card e tipografia |

---

## 4. Princípios de Design

### P1 — Espaço negativo é um componente
Padding de card mínimo de 32px. Gap entre cards de 24px. Margem lateral de 48px.
Se a tela parece vazia, provavelmente está certa.

### P2 — Um número dominante por tela, não por card
Ao contrário de dashboards densos, aqui **a tela inteira** tem um protagonista visual.
Nas outras telas, 32px é o teto — só o protagonista chega a 64px.

### P3 — Paleta dessaturada
Cores vibrantes cansam em sessões longas de análise. A paleta usa saturação
reduzida (~55-65%) mantendo a distinção semântica.

- **Azul suave** → CTL / fitness
- **Coral suave** → ATL / fadiga
- **Verde sálvia** → TSB positivo / recuperado
- **Âmbar suave** → atenção / moderado
- **Cinza-azulado** → dados secundários

### P4 — Tipografia faz o trabalho da cor
Hierarquia primária por tamanho e peso, secundária por cor. Uma tela em escala
de cinza ainda deve ser legível e hierarquizada.

### P5 — Dark mode com profundidade sutil
Três níveis de superfície, com diferenças de luminosidade pequenas (~4%).
Nunca preto puro. Bordas de 1px fazem a separação, não sombras.

### P6 — Densidade progressiva
- Nível 1 — visão da semana: 5 blocos, leitura em 5 segundos
- Nível 2 — drill-down de um dia: drawer lateral, sem sair da tela
- Nível 3 — atividade individual: página dedicada, densidade total permitida

### P7 — Sem chrome
Sem gradientes decorativos, sem sombras, sem ícones sem função, sem bordas duplas.

---

## 5. Telas — Especificação

### 5.1 `/week` — TELA PRINCIPAL

Esta é a tela de entrada do produto. Responde: **"como foi minha semana e como
meu corpo respondeu?"**

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   VeloDNA                                                    ⚙️        │
│                                                                        │
│   ────────────────────────────────────────────────────────────────    │
│                                                                        │
│   SEMANA 14 – 20 ABRIL                      ◀  anterior   próxima ▶   │
│                                                                        │
│                                                                        │
│         412                                                            │
│         TSS na semana          ▲ 12% vs. semana anterior              │
│                                                                        │
│         8h24 tempo  ·  248 km  ·  3.240 m  ·  média 7h18 de sono      │
│                                                                        │
│   ────────────────────────────────────────────────────────────────    │
│                                                                        │
│                                                                        │
│   [ TIMELINE UNIFICADA — treino acima, saúde abaixo ]                 │
│                                                                        │
│                                                                        │
│   ────────────────────────────────────────────────────────────────    │
│                                                                        │
│   ┌────────────────────────┐      ┌────────────────────────────┐     │
│   │  DISTRIBUIÇÃO DE ZONAS │      │  8 SEMANAS                 │     │
│   │                        │      │                            │     │
│   │  Z1 ██████████    42%  │      │   ▁▃▅▄▆▅█▇                │     │
│   │  Z2 ███████       31%  │      │                            │     │
│   │  Z3 ███           12%  │      │   média 368 TSS            │     │
│   │  Z4 ██             9%  │      │   ramp rate +4.2/semana    │     │
│   │  Z5 █              6%  │      │                            │     │
│   └────────────────────────┘      └────────────────────────────┘     │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

**Blocos:** 4 no total (header com número dominante, timeline, zonas, tendência).
O TSS de 412 é o protagonista em 64px. Tudo mais é 32px ou menor.

---

### 5.2 `/` — Dashboard / Hoje

Responde: **"como estou hoje e o que devo fazer?"**

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   HOJE · SEGUNDA, 21 DE ABRIL                                         │
│                                                                        │
│                                                                        │
│              78                                                        │
│              readiness            Apto para treino intenso            │
│                                                                        │
│              ████████████████████████░░░░░░░                          │
│                                                                        │
│                                                                        │
│   ────────────────────────────────────────────────────────────────    │
│                                                                        │
│     Sono          HRV           Forma         Body Battery            │
│     7h42          48ms ▲        TSB +4        87                      │
│     ▲ 0h30        +3 vs média   fresco        recuperado              │
│                                                                        │
│   ────────────────────────────────────────────────────────────────    │
│                                                                        │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │  AI COACH                                                     │   │
│   │                                                               │   │
│   │  Sua carga subiu 12% na última semana e o TSB voltou ao       │   │
│   │  positivo após o bloco de terça. HRV estável em alta.         │   │
│   │  Boa janela para um treino de limiar hoje ou amanhã.          │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                        │
│                                            [ ver semana completa → ]  │
└──────────────────────────────────────────────────────────────────────┘
```

**Blocos:** 3. O readiness de 78 é o protagonista. Whoop-like na hierarquia,
mas com os 4 indicadores de contexto logo abaixo em peso igual entre si.

---

### 5.3 `/fitness` — PMC com camada de saúde

O PMC tradicional, **mais a sobreposição de HRV** — novamente o cruzamento
saúde × treino que nenhum concorrente entrega.

- Gráfico principal: CTL (área azul suave preenchida), ATL (linha coral), TSB (barras abaixo do zero)
- **Camada opcional:** linha de HRV normalizada sobreposta, toggle no canto
- Seletor de período: 30 / 90 / 180 / 365 dias
- Faixas de fundo por zona de TSB:

| Faixa | TSB | Significado |
|---|---|---|
| Cinza | > +25 | Destreinamento |
| Verde sálvia | +5 a +25 | Forma de prova |
| Neutro | −10 a +5 | Equilíbrio |
| Âmbar suave | −30 a −10 | Treino produtivo |
| Coral | < −30 | Risco de overtraining |

- Marcadores verticais para provas e eventos na timeline

---

### 5.4 `/activity/:id` — Atividade Individual

Única tela onde densidade total é permitida — é o nível 3 da progressão.

- Header com métricas principais: distância, tempo, TSS, NP, IF, elevação
- Mapa Leaflet com rota colorida por potência ou gradiente (toggle)
- Gráfico de streams com eixos X sincronizados: potência, FC, cadência, altitude
- **Brush selecionável** — ao selecionar um trecho, todas as métricas recalculam
- Distribuição de zonas da atividade
- W' balance ao longo do tempo
- Contexto de saúde do dia: sono da noite anterior, HRV da manhã
- Análise do AI Coach no rodapé

---

## 6. Design Tokens

```css
:root {
  /* ── Superfícies — 3 níveis, diferença sutil ─────────────── */
  --bg-base:        #12161F;   /* fundo da página */
  --bg-surface:     #181D28;   /* cards */
  --bg-elevated:    #1F2530;   /* drawers, tooltips */
  --border-subtle:  #262D3A;
  --border-strong:  #343D4D;

  /* ── Texto ──────────────────────────────────────────────── */
  --text-primary:   #E8EBF0;   /* não branco puro */
  --text-secondary: #8E99AB;
  --text-tertiary:  #5C6678;

  /* ── Semântica — saturação reduzida ─────────────────────── */
  --ctl:            #5B8DD6;   /* azul suave — fitness */
  --atl:            #D97A6C;   /* coral suave — fadiga */
  --tsb-positive:   #7BA88A;   /* verde sálvia — forma boa */
  --tsb-negative:   #D4A05C;   /* âmbar suave — fadiga */
  --hrv:            #8B9DC7;   /* azul-lavanda — HRV */
  --sleep:          #6B7FA3;   /* azul acinzentado — sono */
  --power:          #9B87B8;   /* roxo suave */
  --hr:             #C48298;   /* rosa dessaturado */

  /* ── Zonas de potência — gradiente frio → quente ────────── */
  --z1: #5C6678;  --z2: #5B8DD6;  --z3: #7BA88A;
  --z4: #D4A05C;  --z5: #D97A6C;  --z6: #9B87B8;

  /* ── Tipografia ─────────────────────────────────────────── */
  --font-sans: 'Inter', -apple-system, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', monospace;

  --text-hero:    4rem;      /* 64px — protagonista da tela, 1 por tela */
  --text-metric:  2rem;      /* 32px — métricas de card */
  --text-lg:      1.125rem;  /* 18px — corpo destacado */
  --text-body:    0.9375rem; /* 15px — corpo padrão */
  --text-label:   0.6875rem; /* 11px — labels uppercase */

  --tracking-label: 0.1em;
  --leading-body:   1.7;     /* generoso, estética calma */

  /* ── Espaçamento — escala 4px, valores altos ────────────── */
  --space-1: 0.25rem;   --space-2: 0.5rem;    --space-3: 0.75rem;
  --space-4: 1rem;      --space-6: 1.5rem;    --space-8: 2rem;
  --space-12: 3rem;     --space-16: 4rem;     --space-20: 5rem;

  --card-padding:   var(--space-8);   /* 32px mínimo */
  --card-gap:       var(--space-6);   /* 24px entre cards */
  --page-margin:    var(--space-12);  /* 48px lateral */
  --section-gap:    var(--space-16);  /* 64px entre seções */

  /* ── Raio ───────────────────────────────────────────────── */
  --radius-sm: 6px;  --radius-md: 12px;  --radius-lg: 20px;
}
```

---

## 7. Layout Desktop

```
Canvas alvo:      1440px
Largura máxima:   1280px (centralizado)
Margem lateral:   48px
Grid:             12 colunas, gutter de 24px

Breakpoints (secundários, sem otimização prioritária):
  ≥ 1440px   layout completo
  1024–1439  cards de 2 colunas viram 1 coluna nas seções inferiores
  < 1024px   stack vertical simples — funcional, não otimizado
```

---

## 8. Padrões de Componente

### 8.1 Número Protagonista (1 por tela)

```
    412                              ← 64px, peso 500, tabular-nums
    TSS na semana    ▲ 12%           ← 15px secondary + delta 13px
```

Sem card, sem borda, sem fundo. Fica solto no espaço da página com
`--space-16` acima e abaixo.

### 8.2 MetricCard

```
┌──────────────────────────────┐
│                              │  ← padding 32px
│  LABEL                       │  ← 11px, uppercase, tracking 0.1em
│                              │
│  48ms              ▲ +3      │  ← 32px peso 500
│  HRV média                   │  ← 15px secondary
│                              │
└──────────────────────────────┘
```

- Borda `1px solid var(--border-subtle)`, raio 12px
- Sem sombra, sem gradiente
- Hover: borda → `--border-strong`, transição 150ms ease

### 8.3 Gráficos (Recharts)

- **Sem gridlines verticais.** Apenas horizontais em `--border-subtle` a 35% de opacidade
- `axisLine={false}` e `tickLine={false}` em todos os eixos
- Ticks em `--text-tertiary`, 11px
- Áreas preenchidas com gradiente vertical 18% → 0%
- Linhas de 2px, sem pontos visíveis exceto no hover
- Tooltip com fundo `--bg-elevated`, borda sutil, sem seta, raio 8px
- Animação de entrada 500ms ease-out apenas no mount

### 8.4 Sparkline semanal

Barras verticais, uma por dia, largura 12px, gap 8px.
Dia sem treino = traço de 2px em `--text-tertiary`.
Dia atual = barra com sublinhado de 2px em `--text-primary`.

---

## 9. Anti-padrões

- ❌ Gauges circulares e velocímetros
- ❌ Pizza para distribuição de zonas — use barras horizontais
- ❌ Mais de 3 séries no mesmo gráfico
- ❌ Mais de 5 blocos visuais numa tela de nível 1
- ❌ Dois números em 64px na mesma tela
- ❌ Cores vibrantes / saturadas
- ❌ Modais para exibir dados — use drawer lateral ou página dedicada
- ❌ Números sem contexto (delta, baseline ou unidade sempre)
- ❌ Separar saúde de treino em abas diferentes — é o problema que o produto resolve
- ❌ Ícones decorativos
- ❌ Scroll horizontal em qualquer largura

---

## 10. Referências para Calibração Visual

Buscar e observar antes de implementar (usar como calibração, não copiar):

**Estética calma + dados**
- Oura app — escala tipográfica, respiro, dessaturação
- Whoop — hierarquia do recovery score, cor semântica
- Athlytic (iOS) — leitura de readiness em 2 segundos

**Dark mode desktop bem resolvido**
- Linear (linear.app) — tipografia, densidade sem ruído
- Vercel Analytics — cards de métrica com delta
- Railway dashboard — hierarquia visual

**Lógica analítica (não o visual)**
- Intervals.icu — estrutura do PMC
- Xert — power curve e MPA
- Runalyze — distribuição de zonas

---

## 11. Prioridade de Implementação

| # | Entrega | Por quê |
|---|---|---|
| 1 | Design tokens + layout base 1280px | Fundação |
| 2 | **Timeline unificada treino × saúde** | Componente-assinatura, resolve as 2 frustrações |
| 3 | Tela `/week` completa | Tela principal do produto |
| 4 | `ReadinessHero` + tela `/` | Entrada diária |
| 5 | `FitnessChart` PMC com camada HRV | Métrica central + diferencial |
| 6 | Distribuição de zonas + tendência 8 semanas | Completa a tela `/week` |
| 7 | `ActivityDetail` + mapa + brush | Nível 3 de profundidade |
| 8 | `CoachCard` | Camada de insight |

---

## 12. Stack de Frontend

```
React 18 + Vite
├── recharts        — linha, área, barra, composed charts
├── leaflet         — mapas de rota (tiles OpenStreetMap)
├── react-leaflet   — binding React
├── axios           — chamadas à FastAPI
└── CSS Modules     — design system próprio, sem framework
```

Sem Tailwind, sem Material UI, sem shadcn. O design system são os tokens da
Seção 6 mais aproximadamente 400 linhas de CSS.

---

## 13. Checklist de Qualidade

Antes de considerar uma tela pronta:

- [ ] Existe exatamente **um** número em 64px?
- [ ] A tela tem no máximo 5 blocos visuais (exceto `/activity/:id`)?
- [ ] O padding de todos os cards é ≥ 32px?
- [ ] Toda cor tem significado semântico da Seção 4?
- [ ] Nenhuma cor está com saturação acima de 65%?
- [ ] Todos os números têm contexto — delta, baseline ou unidade?
- [ ] Os gráficos têm no máximo 3 séries?
- [ ] Funciona em 1280px sem scroll horizontal?
- [ ] Em escala de cinza, a hierarquia ainda é legível?
- [ ] Estados vazios tratados — sem dados vira mensagem, não gráfico quebrado?
- [ ] Loading usa skeleton, nunca spinner?
- [ ] A tela responde à pergunta dela em menos de 5 segundos de leitura?
- [ ] Saúde e treino aparecem juntos onde faz sentido, nunca separados por aba?
