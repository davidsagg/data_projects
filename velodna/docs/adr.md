# VeloDNA — Architecture Decision Records (ADRs)

---

## ADR-001: DuckDB como banco analítico principal

**Status:** Aceito

**Contexto:** O VeloDNA processa séries temporais densas (1 ponto/segundo por atividade) e executa queries analíticas pesadas: agregações por período, médias móveis (CTL/ATL), distribuições de zonas, curvas de potência. É uma aplicação local, single-user, sem necessidade de concorrência multi-processo.

**Decisão:** Usar DuckDB como único banco de dados.

**Consequências:**
- Zero infraestrutura: banco é um único arquivo `.duckdb`.
- Performance colunar nativa para OLAP — 10–100× mais rápido que SQLite para este workload.
- Integração direta com pandas via `duckdb.query().df()`.
- Limitação: single-writer; sem replicação nativa. Mitigação: acesso serializado pela API FastAPI.

---

## ADR-002: FIT files como fonte primária de verdade

**Status:** Aceito

**Contexto:** Dados de ciclismo existem em múltiplos formatos (FIT, GPX, TCX, JSON Strava). O formato FIT (Flexible and Interoperable Data Transfer) é o padrão do ecossistema Garmin/ANT+ e contém a maior densidade de dados brutos (streams segundo a segundo com potência, FC, cadência, GPS).

**Decisão:** Arquivos FIT são a fonte primária; outras fontes (Strava API, GPX) são complementares e nunca sobrescrevem dados FIT.

**Consequências:**
- Dados de potência e streams brutos sempre provêm do FIT quando disponível.
- `fit_file_path` é armazenado em `activities` para auditoria e reprocessamento.
- Importações Strava preenchem metadados mas não sobrescrevem streams FIT.

---

## ADR-003: React + Vite para o frontend

**Status:** Aceito

**Contexto:** O VeloDNA precisa de visualizações interativas (gráficos CTL/ATL, power curve, perfil de elevação) com atualização em tempo real durante imports. A stack de frontend deve ser leve, com build rápido para desenvolvimento local.

**Decisão:** React 18 + Vite como bundler; Recharts para gráficos; TailwindCSS para estilização.

**Consequências:**
- HMR (Hot Module Replacement) instantâneo no desenvolvimento.
- Bundle otimizado para produção com tree-shaking automático.
- Recharts integra nativamente com dados JSON da API FastAPI.
- Fora do escopo das fases atuais de backend; implementado em fase futura.

---

## ADR-004: Ollama para LLM local

**Status:** Aceito

**Contexto:** O AI Coach precisa de um LLM capaz de interpretar dados de treino e gerar análises em linguagem natural. Requisitos: privacidade total (dados de saúde não saem da máquina), zero custo de inferência, operação offline.

**Decisão:** Usar Ollama com `llama3:latest` como modelo padrão; `mistral:latest` como fallback.

**Consequências:**
- Inferência 100% local, dados de saúde nunca saem do ambiente.
- Latência de resposta depende do hardware (GPU recomendada).
- API compatível com OpenAI (`/v1/chat/completions`) facilita eventual migração.
- Host configurável via `OLLAMA_HOST` no `.env`.

---

## ADR-005: garminconnect (lib não-oficial) para dados de saúde

**Status:** Aceito com ressalvas

**Contexto:** A Garmin não oferece API pública oficial para dados de saúde (HRV, sono, body battery, stress). A biblioteca `garminconnect` realiza web-scraping autenticado do Garmin Connect.

**Decisão:** Usar `garminconnect` para sincronização de dados de saúde diários.

**Consequências:**
- Funciona com credenciais padrão Garmin (email + senha via `.env`).
- Risco: Garmin pode alterar a API interna sem aviso, quebrando a integração.
- Mitigação: sync diário em horário fixo; fallback gracioso quando a lib falha.
- Dados importados ficam em `health_daily`; reimportação é sempre possível.

---

## ADR-006: opentopodata API para enriquecimento de elevação

**Status:** Aceito

**Contexto:** Arquivos GPX de rotas planejadas frequentemente têm dados de elevação ausentes ou imprecisos (GPS barométrico vs. topográfico). Análises de gradiente e estratégia de pacing requerem elevação confiável.

**Decisão:** Usar a API pública `opentopodata.org` (dataset SRTM 30m) para enriquecer coordenadas GPS com elevação corrigida.

**Consequências:**
- Enriquecimento automático na importação de GPX quando elevação está ausente.
- Dependência de rede externa; falha silenciosa mantém elevação original do GPX.
- Rate limit: 1 req/s na API pública; lotes de até 100 pontos por request.
- Self-hosting disponível via Docker se privacidade de rotas for requisito.
