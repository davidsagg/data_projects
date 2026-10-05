# VeloDNA — Guia para o Claude Code CLI

Plataforma local de performance ciclística. Privacidade-first: dados de saúde e treino nunca saem do dispositivo.

**Versão atual:** v2.4.0 · **Testes:** 475 passando

> **v2.4.0 (2026-10-01)** — aba **Panorama** (ciclo de 13/26/52 semanas contra as
> metas), inspirada em `docs/design-refs/health_tracker.html`: peso, FTP e W/kg
> (inclusive projetado no peso alvo), volume por modalidade (rua / rolo / força /
> outros) contra a meta semanal, maior esforço frente ao treino típico, CTL com
> marcos, zonas do ciclo, atividades com nome e notas. Metas (`athlete_goals`) e
> marcos (`milestones`: exame, plano, prova, achado) entram por formulário, pela
> API ou pelos scripts. Visual novo: fundo frio no lugar do creme, cards com
> sombra, Manrope/Public Sans/IBM Plex Mono servidas localmente (`@fontsource`),
> botão "Ver como tabela" nos gráficos.
>
> **Dois bugs corrigidos no caminho.** (1) `format.js` lia datas `AAAA-MM-DD` como
> meia-noite UTC — em Brasília, toda data aparecia um dia antes (a semana de 28/09
> mostrava "27 set"). Agora `toDate()` trata data pura como meia-noite local.
> (2) `weekly._aggregate_zones` somava potência de corrida nas zonas de ciclismo;
> agora filtra por `POWER_SPORTS`.

> **v2.3.0 (2026-09-25)** — quatro análises do workflow do post da augo: subidas
> com VAM, execução por quartos, densidade carga interna × externa e perfil de
> capacidade (forças e limitadores contra o próprio recorde).
>
> **Bug de ingestão corrigido.** O `fit_parser` lia `altitude` e `speed`; os
> dispositivos Garmin modernos gravam `enhanced_altitude`/`enhanced_speed` e
> omitem os clássicos. 192 atividades estavam sem altitude e sem velocidade nos
> streams — invisível porque o resumo mostrava a elevação certa (vem da mensagem
> `session`, não dos records). Só apareceu quando a detecção de subidas devolveu
> zero subidas num pedal de 1.570 m. Recuperado com
> `scripts/backfill_stream_channels.py`; cobertura de altitude entre atividades
> com GPS: 593/594.

> **v2.2.0 (2026-09-24)** — camada de feedback subjetivo (RPE, sensação, notas,
> inclusive em dia sem treino) e **servidor MCP somente-leitura** que expõe o
> acervo a um cliente de IA. Ideia vinda do post do Marco Altini sobre o conector
> da augo: o valor não está num assistente embutido, e sim em expor a camada de
> dados para construir as próprias análises. Também: redesign do frontend sobre
> `velodna_design_benchmark_v2.md` — timeline unificada treino × saúde, `/week`
> como tela principal, navegação em funil.

> **v2.1.0 (2026-09-13)** — integração com o Strava (OAuth com rotação de token,
> sync incremental e dedupe contra o acervo `.fit`), visão da semana executada com
> distribuição polarizada, e quatro análises avançadas: detecção de intervalos,
> durabilidade, W'bal corrigido (Skiba) e agregação semanal de zonas.
>
> **Correção de fuso (2026-09-13).** O `fitparse` devolve timestamps naive e o padrão
> FIT grava em UTC; ao entrar numa coluna `TIMESTAMPTZ` o DuckDB presumia o fuso local
> e gravava o instante 3 h à frente. As 634 atividades de `.fit` foram reinterpretadas
> via `scripts/fix_fit_timezone.py`, e o parser passou a rotular UTC (`_as_utc`). Só
> uma atividade mudou de data. O erro ficou invisível por meses porque as datas
> continuavam certas — apareceu quando o Strava trouxe a mesma pedalada com o horário
> verdadeiro e o casamento de ±5 min falhou, duplicando o registro.

> **v2.0.0 (2026-07-25)** — migração do schema legado (`src/ingestion/catalog_store.py`,
> removido) para o schema canônico em `src/storage/`, e reconstrução da fundação analítica:
> NP/IF/VI/EF reais, histórico de eFTP, HRSS calibrado e PMC contínuo.
> Banco anterior preservado em `data/velodna_legacy.duckdb`.

**Escopo dos dados:** por decisão do Dave, o catálogo mantém apenas de **2023 em diante**
(754 atividades, 2023-01-02 a 2026-09-13). As atividades de 2012–2022 foram removidas;
seguem recuperáveis no banco legado, nos `.fit` originais em `data/fit/` e no Strava.

⚠️ **O piso de 2023 é aplicado no código**, em `scripts/sync_strava.py` (`CATALOG_START`).
A conta do Strava tem histórico desde 2012: um `--all` sem o piso reinjeta 1.367
atividades que foram descartadas de propósito. Use `--ignore-scope` só se a intenção
for mesmo trazer tudo.

**Perfil do atleta:** FTP 217 W · FC máx 186 · FC repouso 58 · 73 kg (out/2026). Cadastrado via
`scripts/set_athlete_profile.py`. A FC de limiar (~152 bpm) é calibrada dos dados, não
informada — ver a etapa `calibrate` do recompute.

**Protocolo de teste do atleta:** um teste por ano, em janeiro, com esforços máximos de
**1 min e 12 min** — que é um teste de potência crítica de dois pontos. Registrar com
`--cp-test AAAA-MM-DD`. Testes registrados: 2024-01-20 (CP 218,1 W), 2025-01-25 (206,4 W),
2026-01-31 (218,1 W), com W' entre 16,8 e 17,2 kJ.

**Potência de corrida não entra nas métricas de ciclismo.** O atleta usa medidor de potência
correndo, e a escala é outra: 266 W em 30 min de corrida contra 219 W pedalando. Estimativa de
FTP e curva de potência filtram por `sport_type` (`ftp_history.POWER_SPORTS`, parâmetro `sport`
nos endpoints). Misturar as duas inflava o eFTP em até 25%.

---

## Ambiente

- **Diretório do projeto:** `velodna/` (dev local)
- **Python:** 3.11 · venv em `.venv`
- **Executar testes:** `.venv/bin/pytest tests/ -v`
- **Linter/formatter:** `ruff check src/ tests/` e `ruff format src/ tests/`
- **Banco de dados:** DuckDB — arquivo único em `data/velodna.duckdb` (ignorado pelo git)
- **AI local:** Ollama em `http://localhost:11434` (llama3:latest, fallback mistral:latest)
- **Variáveis de ambiente:** definidas em `.env` (não commitado) — ver `.env.example` se existir

### Scripts de manutenção

```bash
# Importar arquivos .fit em lote (data/fit/)
.venv/bin/python scripts/import_history.py

# Recomputar métricas derivadas — etapas encadeadas, idempotentes
.venv/bin/python scripts/recompute_metrics.py
.venv/bin/python scripts/recompute_metrics.py --stage curves,metrics

# Cadastrar perfil do atleta e/ou cortar histórico
.venv/bin/python scripts/set_athlete_profile.py --ftp 217 --max-hr 186 \
    --resting-hr 58 --weight 71 --drop-before 2023-01-01

# Registrar um teste de potência crítica (protocolo 1 min + 12 min)
.venv/bin/python scripts/set_athlete_profile.py --cp-test 2026-01-31

# Metas (repetível): metrica=valor[@prazo]; valor vazio remove
# métricas: weight_kg, weekly_hours, ftp_w, w_per_kg, ctl
.venv/bin/python scripts/set_athlete_profile.py --goal weight_kg=68 --goal weekly_hours=10

# Marcos: exames, planos, provas, achados (testes de CP entram sozinhos)
.venv/bin/python scripts/add_milestone.py --date 2026-02-12 --kind exame \
    --title "Ergoespirometria" --measure vo2max_ml_kg_min=47.5 --summary "..."
.venv/bin/python scripts/add_milestone.py --list

# Sincronizar saúde do Garmin — incremental e retomável
.venv/bin/python scripts/sync_garmin_health.py --days 30
.venv/bin/python scripts/sync_garmin_health.py --start 2023-06-24 --end 2026-06-25
```

```bash
# Strava — autorização inicial (uma vez, abre o navegador)
.venv/bin/python scripts/authorize_strava.py

# Strava — sincronização incremental (o padrão busca só o que falta)
.venv/bin/python scripts/sync_strava.py
.venv/bin/python scripts/sync_strava.py --days 90
.venv/bin/python scripts/sync_strava.py --check        # só valida a credencial
.venv/bin/python scripts/sync_strava.py --dry-run      # lista sem gravar
```

**Strava:** o refresh token **rotaciona a cada renovação** — o antigo morre. Por isso
os tokens vivem em `~/.velodna/strava_token.json` (gravado atomicamente antes de o
access token ser devolvido), e não no `.env`, que só serve de semente. O `.env` guarda
apenas `STRAVA_CLIENT_ID` e `STRAVA_CLIENT_SECRET`.

O acervo já tem as mesmas pedaladas vindas dos `.fit`. O sync casa por horário de
início (±5 min) e **anota o `strava_id` no registro existente** em vez de inserir
cópia — duplicar envenenaria o PMC, contando o TSS de cada dia em dobro. Rate limit:
100 requisições / 15 min e 1.000 / dia; ao receber 429 o cliente dorme até a virada
da janela. Depois de sincronizar, rode `recompute_metrics.py`.

**Nome e modalidade vêm do Strava.** O sync grava `name`, `strava_sport_type` e
`trainer` em toda atividade que passa por ele — inclusive nas já sincronizadas —,
então reanotar o acervo é `sync_strava.py --start 2023-01-01 --no-streams`. A
modalidade (rua / rolo / força / outros) sai de `analytics.modality.classify`:
o `.fit` diz `cycling` para rua e rolo, e as duas coisas não são o mesmo treino.

**Peso do Garmin vem das pesagens, não de `get_stats`.** O campo `weight` que o
builder diário procurava nunca vem preenchido; o peso mora em
`get_body_composition` (balança ou lançamento manual no app). O sync busca as
pesagens de `--weight-days` (365) numa requisição só, a cada execução. O Panorama
usa a pesagem dos últimos 30 dias; sem ela, o cadastro do atleta.

**Exames ficam em `docs/dados-saude/`, fora do git** (o monorepo é público). Os
valores entram no banco como marco (`add_milestone.py`) — e só lá: nem os
números do laudo vão para arquivo versionado. A ergoespirometria + lactato de
fev/2026 já está registrada.

**Garmin:** o backfill longo leva ~1 s por dia e o Garmin bloqueia por IP (429).
A sessão é persistida em `~/.garminconnect` para evitar relogar. O script só busca
dias ausentes, então pode rodar em lotes.

Etapas de `recompute_metrics.py`, na ordem de dependência:
`curves` (MMP por atividade) → `metrics` (NP/VI/EF/decoupling, independem de FTP) →
`ftp` (histórico de eFTP a partir das curvas) → `load` (IF/TSS com o FTP da época + HRSS) →
`calibrate` (ajusta a âncora de FC comparando HRSS com TSS de potência, e reprocessa) →
`zones` (materializa as zonas por ponto de FTP) → `pmc` (série de CTL/ATL/TSB).
O ciclo completo leva ~40 s para 1.470 atividades.

**DuckDB aceita um único escritor.** Um backfill longo que segure a conexão bloqueia
qualquer outro processo — por isso `sync_garmin_health.py` grava em lotes (`--batch`),
abrindo e fechando a conexão a cada lote.

### Servidor MCP

```bash
make api          # noutro terminal — o MCP fala HTTP com ela
make mcp          # servidor em stdio
```

Já configurado em `.mcp.json`, então o Claude Code no diretório do projeto o
carrega sozinho. 17 ferramentas: perfil do atleta, semana, série de semanas,
atividades, análise completa de atividade, W'bal, carga, curva de potência,
histórico de FTP, eficiência, saúde, feedback subjetivo, insights, segmentos,
panorama do ciclo, metas e marcos.

**Fala HTTP com a API, nunca com o DuckDB.** Não é preferência de estilo: o banco
aceita um escritor só, e com a API de pé nem `duckdb.connect(read_only=True)`
consegue abrir o arquivo. Um MCP que tocasse o banco direto brigaria com a API
justamente quando os dois precisam rodar juntos.

**Somente leitura, por decisão.** `tests/unit/test_mcp_server.py` tem um teste que
falha se alguém acrescentar uma ferramenta com verbo de escrita no nome.

### Iniciar serviços

```bash
# API (porta 8006, conforme o mapa de portas do monorepo)
DB_PATH=data/velodna.duckdb .venv/bin/uvicorn api.main:app --port 8006 --app-dir src --reload

# Frontend React (porta 5176; proxeia /api para 8006)
cd frontend && npm run dev

# Airflow + MLflow: o docker-compose ficava no .devcontainer (removido na migração local).
# Recriar um docker-compose.yml no projeto se precisar orquestrar (não é necessário p/ o core).
```

---

## Stack e ADRs

| Decisão | Escolha | ADR |
|---|---|---|
| Banco de dados | DuckDB embarcado (arquivo único, OLAP, zero infra) | `docs/adr/ADR-001-duckdb.md` |
| Inferência de IA | Ollama local (llama3/mistral, privacidade total) | `docs/adr/ADR-002-ollama-local-ai.md` |
| API | FastAPI + uvicorn | — |
| Frontend | React 19 + Vite + Recharts + react-leaflet | — |
| Orquestração | Apache Airflow 3.x DAGs em `dags/` | — |
| Transformações SQL | dbt-duckdb em `dbt/` | — |
| Experiment tracking | MLflow (backend local `mlflow/mlruns/`) | — |

---

## Estrutura do projeto

```
src/
  ingestion/       ← fit_parser, gpx_loader, garmin_health_client, pipeline,
                      strava_auth (OAuth + rotação), strava_client, strava_sync (dedupe)
  storage/         ← CatalogStore (DuckDB DDL + CRUD), models (Activity/ActivityStream),
                      query (rows/row — nomes de coluna do resultado, não da conexão)
  analytics/       ← timeseries (base), power_metrics (NP/IF/VI/EF), hr_metrics (HRSS/TRIMP/
                      decoupling), ftp_history (eFTP), critical_power (CP/W'),
                      zones (Coggan, derivadas do limiar vigente),
                      intervals (detecção de blocos), durability (fadiga-resistência),
                      climbs (detecção + VAM), pacing_analysis (quartos + densidade),
                      capacity (forças e limitadores),
                      wbal_terrain (W'bal × percurso: onde o tanque esvaziou),
                      modality (rua/rolo/força/outros), goals (progresso e
                      sentido de cada meta), panorama (ciclo de N semanas),
                      weekly (semana executada + polarização),
                      PMCCalculator, PowerCurveEngine, WPrimeModel (Skiba),
                      VeloDNATracker (MLflow)
planning/          ← projection (PMC para frente), calendar (planejado x realizado)
  mcp_server/      ← servidor MCP (stdio) sobre a API — somente leitura
  api/             ← FastAPI app + 9 routers (activities, analytics, fitness, planning,
                      health, routes, segments, training, export, coach)
  routes/          ← GPXAnalyzer, SegmentClassifier, PacingStrategy, TimeEstimator
  health/          ← SleepCorrelator, HRVTrendAnalyzer, ReadinessCalculator
  ai/              ← OllamaClient, ContextBuilder, PostActivityCoach, WeeklyPlanCoach
frontend/                        ← reescrito na v2.0.0; os componentes antigos foram
  src/                             removidos (referenciavam campos do schema legado)
    App.jsx                      ← casca: navegação e alternador de tema
    styles/tokens.css            ← tokens de design; paleta validada nos dois temas
    lib/
      api.js                     ← único lugar que conhece endpoints e campos
      format.js                  ← formatadores pt-BR
      useCssVar.js               ← lê tokens CSS (o Recharts precisa de string, não var())
    components/viz/              ← ChartFrame, Tooltip, StatTile
    components/fitness/          ← PMCChart, PowerCurveChart, FTPHistoryChart,
                                   EfficiencyChart
    components/health/           ← ReadinessHero, HRVChart, WellnessChart
    components/activity/         ← ActivityPicker, ActivityDetail, ActivityCompare
    components/training/         ← IntensityBar, WeekLoadChart, WBalChart/WBalPanel,
                                   IntervalPanel, DurabilityPanel
    components/panorama/         ← VolumeChart, CtlChart, MilestoneCards, CycleSettings
    components/viz/GoalPill.jsx  ← etiqueta de meta/estado (ícone + texto + fundo)
    components/viz/StatCell.jsx  ← card compacto: valor + etiqueta de tom + ⓘ com a régua
    components/week/WeekGrid.jsx ← semana em grade densa (dias × sinais), saúde
                                   tingida contra a média de 45 dias do atleta
    components/viz/milestoneLines.jsx ← marcos como linhas verticais nos gráficos
    lib/goals.js                 ← texto de meta e tokens de modalidade
    components/fitness/FitnessSection.jsx ← os meses (era a aba Fitness), no fim do Resumo
    views/                       ← SummaryView (hoje + semana + meses), PanoramaView
                                   (ciclo e metas), ActivityView (W'bal sobre o
                                   percurso em destaque, logo após os números)

Três abas: Resumo, Panorama, Atividade. Coach, Plano e Segmentos saíram da
interface (2026-10-02) para focar no uso real; os endpoints continuam na API e,
no caso dos segmentos, no MCP.

Três abas, todas ligadas ao backend real.
tests/
  unit/            ← 22 arquivos de teste (338 casos)
  integration/     ← pipeline end-to-end
  fixtures/        ← sample.fit, sample.gpx, sample_invalid.fit
dags/
  fit_sync_dag.py        ← velodna_fit_sync: scan → parse FIT → update_metrics (@daily)
  health_sync_dag.py     ← velodna_health_sync: sync Garmin health (@daily)
dbt/
  dbt_project.yml
  models/
    weekly_summary.sql   ← TSS e km por semana
    athlete_profile.sql  ← join athlete_metrics + health_daily
docs/
  adr/             ← ADR-001 (DuckDB), ADR-002 (Ollama)
  architecture/    ← erd.md, system-flow.md
  user-stories/    ← 18 US em 4 módulos
data/              ← fit/, gpx/, velodna.duckdb (ignorados pelo git)
```

---

## API REST — endpoints implementados

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/health` | Healthcheck |
| GET | `/activities` | Lista atividades (filtro `start`, `end`) |
| GET | `/activities/latest` | Atividade mais recente |
| GET | `/activities/{id}/streams` | Streams GPS decimados (`every_n`) |
| GET | `/activities/{id}/zones` | Distribuição por zona de potência Coggan |
| GET | `/activities/{id}/power-curve` | Curva MMP de uma única atividade (comparação) |
| POST | `/activities/ingest/fit` | Upload .FIT → persiste + recalcula PMC |
| GET | `/pmc` | Série histórica CTL/ATL/TSB |
| GET | `/power-curve` | Curva MMP agregada (`start`, `end`, `sport`) |
| GET | `/critical-power` | Ajuste de CP e W' na janela (`days`, `sport`) |
| GET | `/ftp-history` | Evolução do FTP, com origem (teste / manual / estimado) |
| GET | `/health-daily` | Últimos N registros de saúde Garmin |
| GET | `/readiness/today` | Score de recuperação do dia |
| GET | `/efficiency` | Série de Efficiency Factor e decoupling |
| GET | `/decoupling` | Deriva cardíaca nos treinos longos |
| GET | `/zones/definitions` | Zonas de potência e FC vigentes numa data |
| GET | `/activities/{id}/zone-distribution` | Tempo em zona (potência + FC) |
| GET | `/week` | Semana executada (seg–dom): volume, aderência, polarização |
| GET | `/weeks` | Série das últimas N semanas |
| GET | `/activities/{id}/intervals` | Blocos de esforço detectados, agrupados em séries |
| GET | `/activities/{id}/wbal` | Balanço de W' (Skiba), com pontos alinhados a tempo/km/altitude e os trechos com o tanque abaixo de 25% |
| GET | `/activities/{id}/durability` | Potência e EF antes/depois de X kJ acumulados |
| GET | `/activities/{id}/climbs` | Subidas com VAM, inclinação e potência |
| GET | `/activities/{id}/pacing` | Distribuição de intensidade por quarto do esforço |
| GET | `/activities/{id}/load-density` | Densidade potência × FC |
| GET | `/capacity-profile` | Forças e limitadores por duração |
| GET | `/panorama` | Ciclo de N semanas (`weeks`, `zones`): atleta, metas, volume, zonas, marcos |
| GET | `/goals` | Metas com valor atual, quanto falta e estado |
| PUT | `/goals` | Cria/substitui a meta de uma métrica |
| DELETE | `/goals/{metric}` | Remove uma meta |
| GET | `/milestones` | Marcos (exame, plano, prova, achado) |
| POST | `/milestones` | Registra um marco |
| DELETE | `/milestones/{id}` | Remove um marco |
| GET | `/feedback` | Feedback subjetivo do período |
| GET | `/activities/{id}/feedback` | Feedback de uma atividade |
| PUT | `/feedback` | Grava/atualiza feedback (idempotente por atleta+data+atividade) |
| DELETE | `/feedback/{id}` | Remove um feedback |
| GET | `/calendar` | Planejado x realizado, dia a dia |
| POST | `/planning/workouts` | Cria treino planejado |
| POST | `/planning/reconcile` | Liga planejado à atividade executada |
| POST | `/planning/projection` | Projeta CTL/TSB por carga semanal ou CTL alvo |
| POST | `/planning/projection/from-plan` | Projeta a partir do calendário |
| POST | `/routes/analyze` | Upload GPX → perfil de elevação |
| POST | `/coach/analyze-activity` | Análise de atividade via Ollama |
| POST | `/coach/chat` | Chat livre com contexto do atleta (US-14) |
| GET | `/coach/chat/{session_id}` | Histórico de uma conversa |
| GET | `/coach/chat-sessions` | Sessões de conversa |
| GET | `/segments` | Segmentos pessoais com resumo das passagens |
| POST | `/segments` | Cria segmento a partir de trecho de atividade |
| POST | `/segments/{id}/rescan` | Reprocessa o histórico à procura de passagens |
| GET | `/segments/{id}/efforts` | Histórico de passagens, ordenado por tempo |
| GET | `/health/sleep-correlation` | Correlação recuperação × performance com n e p (US-12) |
| GET | `/export/activities.csv` | Resumo das atividades em CSV (US-05) |
| GET | `/export/training-load.csv` | Série de CTL/ATL/TSB em CSV |
| GET | `/export/health.csv` | Métricas diárias de saúde em CSV |
| GET | `/export/power-curve.csv` | Curva de potência em CSV |
| GET | `/export/activities/{id}/streams.csv` | Série temporal completa em CSV |

---

## Schema do banco (DuckDB)

DDL completo em `src/storage/catalog_store.py` (`_DDL`). Chaves são UUID.

- `athletes` — perfil do atleta (FTP, peso, FC max)
- `activities` — resumo por atividade: `normalized_power_w`, `intensity_factor`,
  `variability_index`, `efficiency_factor`, `decoupling_pct`, `tss`, `tss_source`
  (`power`/`hr`), `hrss`, `ftp_w_at_time`, `moving_time_s`
- `activity_streams` — série temporal com `time_s` relativo ao início (power, hr_bpm,
  cadência, GPS, altitude)
- `health_metrics` — métricas diárias Garmin (HRV, sono, FC repouso, body battery, VO2max)
- `training_load` — CTL / ATL / TSB / `daily_tss` por data, série diária **contínua**
- `ftp_history` — evolução do eFTP (`effective_from`, `ftp_w`, `method`)
- `power_curves` — melhores potências por duração, por atividade (MMP)
- `power_zones` / `hr_zones` — zonas com `effective_from`
- `routes` + `route_waypoints` + `route_segments` — rotas GPX e perfil de elevação
- `segments` + `segment_efforts` — segmentos pessoais e histórico de passagens
- `activity_feedback` — RPE (Borg 1–10), sensação (1–5), notas. `activity_id`
  **opcional**: nulo é a nota do dia, que é como um dia de descanso entra no
  registro e explica o treino seguinte
- `athlete_goals` — uma meta por métrica (`weight_kg`, `weekly_hours`, `ftp_w`,
  `w_per_kg`, `ctl`). O sentido ("menor é melhor" no peso) mora em `analytics.goals`
- `milestones` — exames, planos, provas e achados, com `measurements` em JSON.
  Os testes de CP **não** vão aqui: o panorama os lê de `ftp_history`
- `activities.name` / `strava_sport_type` / `trainer` — metadados do Strava
  (colunas acrescentadas por `ALTER TABLE ... IF NOT EXISTS` no DDL)
- `ai_conversations` + `ai_insights` — histórico do AI Coach

**Um atleta por instalação:** `CatalogStore.resolve_athlete_id()` é o único ponto que
faz a ponte entre a plataforma single-user e o schema multi-atleta.

---

## Status de implementação

| Módulo | Arquivo(s) | Status |
|---|---|---|
| Storage (DuckDB) | `src/storage/catalog_store.py` | ✅ Completo |
| Parser FIT | `src/ingestion/fit_parser.py` | ✅ Completo |
| Loader GPX | `src/ingestion/gpx_loader.py` | ✅ Completo |
| Cliente Garmin | `src/ingestion/garmin_health_client.py` | ✅ Completo |
| Cliente Strava | `src/ingestion/strava_client.py` | ✅ Completo (paginação + rate limit) |
| OAuth Strava | `src/ingestion/strava_auth.py` | ✅ Completo (rotação persistida) |
| Sync Strava | `src/ingestion/strava_sync.py` + `scripts/sync_strava.py` | ✅ Completo (dedupe) |
| Pipeline de ingestão | `src/ingestion/pipeline.py` | ✅ Completo |
| PMC Calculator (CTL/ATL/TSB) | `src/analytics/pmc_calculator.py` | ✅ Completo |
| Power Curve Engine | `src/analytics/power_curve_engine.py` | ✅ Completo |
| Zone Analyzer (Coggan) | `src/analytics/zone_analyzer.py` | ✅ Completo |
| W' Prime Model | `src/analytics/wprime_model.py` | ✅ Completo |
| FTP Detector | `src/analytics/pmc_calculator.py` (FTPDetector) | ✅ Completo |
| MLflow Tracker | `src/analytics/mlflow_tracker.py` | ✅ Completo |
| GPX Analyzer | `src/routes/gpx_analyzer.py` | ✅ Completo |
| Segment Classifier | `src/routes/segment_classifier.py` | ✅ Completo |
| Pacing Strategy | `src/routes/pacing_strategy.py` | ✅ Completo |
| Time Estimator | `src/routes/time_estimator.py` | ✅ Completo |
| Sleep Correlator | `src/health/sleep_correlator.py` | ✅ Completo |
| HRV Trend Analyzer | `src/health/hrv_trend.py` | ✅ Completo |
| Readiness Calculator | `src/health/readiness.py` | ✅ Completo |
| Ollama Client | `src/ai/ollama_client.py` | ✅ Completo |
| Context Builder | `src/ai/context_builder.py` | ✅ Completo |
| Post Activity Coach | `src/ai/post_activity_coach.py` | ✅ Completo |
| Weekly Plan Coach | `src/ai/weekly_plan_coach.py` | ✅ Completo |
| FastAPI app + routers | `src/api/` | ✅ Completo |
| Frontend React (8 componentes) | `frontend/src/` | ✅ Completo |
| Airflow DAGs | `dags/` | ✅ Completo |
| dbt models | `dbt/models/` | ✅ Completo |
| Zonas de potência e FC | `src/analytics/zones.py` | ✅ Completo |
| Modelo CP/W' | `src/analytics/critical_power.py` | ✅ Completo |
| Detecção de intervalos | `src/analytics/intervals.py` | ✅ Completo |
| Durabilidade | `src/analytics/durability.py` | ✅ Completo |
| Semana executada + polarização | `src/analytics/weekly.py` | ✅ Completo |
| W'bal (Skiba, ciente de pausas) | `src/analytics/wprime_model.py` | ✅ Completo |
| Projeção de carga | `src/planning/projection.py` | ✅ Completo |
| Calendário planejado x realizado | `src/planning/calendar.py` | ✅ Completo |
| Garmin health (real) | `src/ingestion/garmin_health_client.py` | ✅ Completo |
| US-04 Comparação de atividades | `frontend/src/components/activity/ActivityCompare.jsx` | ✅ Completo |
| US-05 Exportação CSV | `src/api/routers/export_router.py` (5 exportações) | ✅ Completo |
| US-07/08 Segmentos pessoais | `src/routes/segment_matcher.py` + `/segments` | ✅ Completo |
| US-12 Correlação sono/performance | `src/health/sleep_correlator.py` + `GET /health/sleep-correlation` | ✅ Completo |
| US-13 Alerta overreaching | `src/health/overreaching_alerts.py` + `GET /health/alerts` | ✅ Completo |
| US-14 Chat livre com coach | `src/ai/chat_coach.py` + `POST /coach/chat` | ✅ Completo |
| US-16 Periodização semanal | `POST /coach/weekly-plan` | ✅ Completo |
| US-17 Nutrição para treinos longos | `POST /coach/nutrition-advice` | ✅ Completo |
| US-18 Risco de lesão | `src/ai/injury_risk_coach.py` + `POST /coach/assess-injury-risk` + DAG semanal | ✅ Completo |

---

## User Stories e módulos

18 User Stories em 4 módulos — ver `docs/user-stories/user-stories.md`.

- **Módulo 1 — Training Analytics** (US-01 a US-05): upload FIT/GPX ✅, zonas de potência ✅, CTL/ATL/TSB ✅, comparação de atividades ⏳, exportação CSV ⏳
- **Módulo 2 — Route Intelligence** (US-06 a US-09): perfil de elevação ✅, segmentos pessoais ⏳, histórico em segmentos ⏳, pacing strategy ✅ (backend)
- **Módulo 3 — Health Insights** (US-10 a US-13): HRV trend ✅, recovery score ✅, correlação sono/performance ⏳, alerta overreaching ✅
- **Módulo 4 — AI Coach** (US-14 a US-18): chat livre ⏳, insight pós-atividade ✅, periodização semanal ✅, nutrição ✅, risco de lesão ✅

---

## Convenções de código

- **Imports:** `from __future__ import annotations` em todo arquivo Python
- **Tipagem:** type hints obrigatórios em todas as funções públicas
- **Docstrings:** estilo Google, em português
- **Testes:** pytest + pytest-asyncio; fixtures em `tests/fixtures/`
- **Linting:** ruff com `line-length = 88`, `target-version = "py311"`
- **Sem mocks do banco:** testes de integração usam DuckDB real (in-memory) — não mockar a camada de storage

---

## Padrão de implementação de uma nova rota

1. Criar o endpoint em `src/api/routers/<módulo>.py` com FastAPI router
2. Registrar o router em `src/api/main.py`
3. Usar `CatalogStore` via dependency injection (`get_db`) — nunca abrir conexão direta
4. Computar métricas via funções de `src/analytics/` ou `src/health/` — nunca inline na rota
5. Escrever teste em `tests/unit/test_api.py` antes de considerar concluído

---

## Contexto importante

- **CatalogStore único:** `src/storage/catalog_store.py`. O duplicado em `src/ingestion/` foi
  removido na v2.0.0 — era ele que continha os dados, enquanto o de `storage/` estava morto e
  quebrado (importava campos inexistentes). O schema de `storage/` venceu por ser melhor
  modelado; os dados foram migrados via `scripts/migrate_to_storage_schema.py`.
- **Modelo de domínio:** `src/storage/models.py` — `Activity`/`ActivityStream` com tempo
  relativo (`time_s`). O `ingestion/fit_parser.py` devolve um DTO cru com timestamp absoluto;
  `activity_from_fit()` faz a ponte. Não misturar os dois.
- **Imports sem prefixo `src.`:** o pacote é publicado com `where = ["src"]`, então
  `from storage.catalog_store import ...`. Misturar `src.storage` e `storage` cria duas
  instâncias distintas do mesmo módulo.
- **Pausas nas séries temporais:** nunca tratar streams como array contíguo. Usar
  `analytics/timeseries.load_series()`, que separa a atividade em segmentos contínuos.
  Janelas móveis (NP, MMP, decoupling) não podem atravessar uma pausa.
- **Airflow 3.x:** usar `schedule=` (não `schedule_interval=`) e `airflow.providers.standard.operators.python.PythonOperator`
- **MLflow:** o backend `FileStore` deixou de ser aviso e passou a erro fatal — o tracking
  usa SQLite (`MLFLOW_TRACKING_URI=sqlite:///mlflow/mlflow.db`)
- **Artefatos de sensor:** o histórico tem picos de 3609 W e 239 bpm. `timeseries.PLAUSIBLE_RANGE`
  descarta valores fora da faixa fisiológica antes de qualquer cálculo
- **Nunca ler `db.description` depois do `execute`:** o atributo pertence à conexão e reflete o
  último comando executado nela. Com requisições concorrentes, um endpoint monta a resposta com
  os nomes de coluna de outro — silenciosamente. Usar `api/query.py` (`rows`/`row`), que lê do
  objeto de resultado. `get_db()` também devolve um `cursor()` por requisição, não a conexão
  compartilhada
- **Cores dos gráficos vêm dos tokens CSS**, lidos via `useCssVar`. A paleta foi validada como
  conjunto (separação para daltonismo, faixa de luminosidade, contraste) nos dois temas — não
  trocar um hex isolado. As modalidades (`--mod-*`) foram validadas à parte; o verde e o
  laranja do claro foram escurecidos até 3:1 sobre o branco
- **Datas puras da API (`AAAA-MM-DD`) passam por `format.toDate`.** `new Date("2026-07-06")`
  é meia-noite UTC e, em Brasília, vira o dia anterior
- **O feedback subjetivo é a única fonte não medida do acervo.** Tudo o mais vem
  de sensor. É ele que explica o treino fraco com HRV normal e sono bom — sem
  ele, o outlier fica sem causa. `upsert_feedback` preserva campos omitidos: quem
  grava só o RPE depois não apaga a nota escrita antes
- **Campos `enhanced_*` do FIT.** Garmin moderno grava `enhanced_altitude` e
  `enhanced_speed` e **omite** os clássicos. `_first_value` tenta o enhanced e cai
  para o antigo. Erro desse tipo é silencioso: o resumo da atividade vem da
  mensagem `session`, então a elevação continua certa enquanto os streams estão
  vazios — só uma análise que dependa do stream acusa
- **Suavizar série com `np.convolve(mode="same")` zera as bordas.** Numa série de
  altitude que começa a 722 m, isso fabricava uma subida fantasma de 384 m a 100%
  de inclinação. Usar padding de borda (`np.pad(mode="edge")`), como em
  `intervals._smooth` e `climbs._smooth`
- **Timestamps de FIT são UTC.** `fitparse` devolve naive; `ingestion.fit_parser._as_utc`
  rotula antes de persistir. Nunca gravar datetime sem fuso numa coluna `TIMESTAMPTZ` —
  o DuckDB presume o fuso da máquina e o erro é silencioso
- **Dedupe do Strava:** `upsert_activity` só deduplica por `garmin_id`. O sync do
  Strava usa `find_activity_near()` (±5 min no horário de início) para casar com o
  que veio dos `.fit` e chama `attach_strava_id()`. Nunca inserir direto o que o
  Strava devolve sem passar por esse casamento
- **NP/IF/VI/TSS não vêm do Strava.** O `weighted_average_watts` deles usa regra
  própria que ignora pausas. O sync deixa os campos vazios e `recompute_metrics.py`
  calcula tudo sob o mesmo critério
- **W'bal tem um valor por segundo em movimento, não por segundo decorrido.**
  Desenhá-lo contra o tempo total (índice × duração ÷ pontos) desloca cada
  mergulho a cada pausa. Use os `points` de `/wbal`, que trazem `t`, `km` e `alt`
  reais (`analytics.wbal_terrain`). A decimação guarda o menor W' de cada balde —
  amostrar um a cada N apagava os fundos, que são o que se quer ver
- **Detecção de intervalos acha terreno, não só treino.** Num pedal de montanha cada
  subida vira um bloco; o `IntervalPanel` só exibe "séries" quando há repetição real
  (`count > 1`), para não inventar prescrição onde houve só relevo. O limiar padrão
  (0,88 × FTP) é ajustável por query param
- **Durabilidade pode ser inconclusiva, e isso é resposta.** Sem `MIN_SIDE_DURATION_S`
  de cada lado do corte de kJ, devolve `is_conclusive: false` — um veredito calculado
  sobre 20 min de pedal pareceria informação sem ser
- **`storage/query.py` é o helper canônico** de `rows`/`row`. `api/query.py` apenas
  reexporta. Qualquer camada que monte dicionário a partir de `execute` deve usá-lo —
  `planning/calendar.py` lia `conn.description` e foi corrigido na v2.1.0
- Arquivos `.fit` e `.gpx` ficam em `data/fit/` e `data/gpx/`
- O banco `velodna.duckdb` fica em `data/` — nunca commitado
- **RouteMap:** usa `GET /activities/{id}/streams?every_n=6` — streams decimados para performance no mapa
- **ZoneChart:** usa `GET /activities/{id}/zones` — FTP buscado de `athlete_metrics` (mais recente com `ftp_w IS NOT NULL`)
