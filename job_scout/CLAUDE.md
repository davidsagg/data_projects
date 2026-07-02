# job_scout

Agente de monitoramento de oportunidades no Freelancer.com via RSS,
com scoring por IA (Claude API) e notificações via Telegram.

Stack: Python 3.11, feedparser, anthropic SDK, httpx, SQLite, PyYAML.

Fluxo: RSS → filtro budget (skip hourly + sem-budget) → score Claude → proposta Claude → Telegram.

Score threshold: 7/10. Budget alvo: $50–500.

Nichos: analytics_consulting, music_automation, music_production, no_tech_automation.

Fonte de dados: rss-freelancer.vercel.app
  Formato de URL: https://rss-freelancer.vercel.app/jobs/<keyword_com_underscores>
  Nota: Upwork RSS foi descontinuado em agosto/2024.
  Budget vem no início do campo summary como "$XXX\nAverage bid<br>...".

## Estrutura

```
job_scout/
├── CLAUDE.md
├── .env / .env.example
├── .gitignore
├── requirements.txt
├── feeds.yaml             — feeds RSS por nicho (18 feeds em 4 nichos)
├── config.py              — variáveis de ambiente, constantes e PROFILE_SUMMARY
├── database.py            — SQLite: init_db, is_seen, save_job
├── rss_fetcher.py         — fetch_all_jobs: busca, deduplica e filtra por budget
├── job_scorer.py          — score_job: retorna JSON estruturado via Claude API
├── proposal_generator.py  — generate_proposal: rascunho em inglês via Claude API
├── telegram_notifier.py   — send_job_notification: mensagem formatada com Markdown
└── main.py                — run_pipeline: orquestra o fluxo completo
```

## Variáveis de ambiente (.env)

| Variável                | Padrão | Descrição                          |
|-------------------------|--------|------------------------------------|
| ANTHROPIC_API_KEY       | —      | Chave da API Anthropic             |
| TELEGRAM_BOT_TOKEN      | —      | Token do bot Telegram              |
| TELEGRAM_CHAT_ID        | —      | ID do chat para notificações       |
| SCORE_THRESHOLD         | 7      | Score mínimo para notificar        |
| BUDGET_MIN              | 50     | Budget mínimo em USD (fixed-price) |
| BUDGET_MAX              | 500    | Budget máximo em USD (fixed-price) |

## Modelo Claude

`claude-opus-4-5` (definido em `config.py::CLAUDE_MODEL`)

## Feeds RSS (feeds.yaml)

**analytics_consulting** (5 feeds):
- Dashboard Python, Data Visualization, Plotly Dashboard, Python Data Analysis, ETL Pipeline

**music_automation** (3 feeds):
- Spotify API, Music Data, Music Automation

**music_production** (6 feeds):
- Music Production, Beat Making, Audio Mixing, Audio Mastering, Audio Engineering, Session Musician

**no_tech_automation** (4 feeds):
- Python Automation Script, Google Sheets Script, Excel Automation, Workflow Automation

## Pipeline (main.py::run_pipeline)

1. `init_db()` (idempotente, sempre chamado no início do pipeline)
2. `fetch_all_jobs()` — parseia feeds, deduplica por MD5 da URL, descarta hourly e jobs sem budget detectado, filtra range `[BUDGET_MIN, BUDGET_MAX]`
3. Filtra jobs já vistos via `is_seen(job_id)` no SQLite
4. Para cada job novo:
   - `score_job(job)` → JSON com score, justification, complexity, estimated_hours, red_flags, detected_niche
   - Se score >= SCORE_THRESHOLD: `generate_proposal()` → `send_job_notification()` (em try interno)
   - `save_job()` com status `notified`, `notify_failed`, `low_score` ou `error`
   - Proposta é preservada no SQLite mesmo se o envio do Telegram falhar (status `notify_failed`)

Execução: **one-shot** (`python main.py`). Sem scheduler — agendamento é responsabilidade externa (cron, systemd timer, etc.).

## Banco de dados (SQLite — job_scout.db)

Tabela `jobs`:
- `job_id` TEXT PK (MD5 da URL)
- `title`, `url`, `budget`, `description` TEXT
- `feed_label`, `niche` TEXT
- `score` INTEGER
- `proposal_draft` TEXT
- `status` TEXT (`notified` | `notify_failed` | `low_score` | `error`)
- `created_at` TIMESTAMP

## Scorer (job_scorer.py)

Retorna JSON com campos:
- `score` int 0–10
- `justification` string (2 frases)
- `complexity` `low|medium|high`
- `estimated_hours` int
- `red_flags` list[str]
- `detected_niche` `analytics_consulting|music_automation|music_production|no_tech_automation`

Score alto (7–10): descrição vaga, cliente sem maturidade técnica, budget real pro escopo.
Score baixo (0–6): ML avançado exigido, budget irreal, stack incompatível.

## Notificação Telegram (telegram_notifier.py)

Formato Markdown com:
- Emoji de score: `🔥🔥` (≥9) / `🔥` (≥7) / `✅`
- Ícone de nicho: `🎸` music_automation / `🎚️` music_production / `📊` analytics / `⚙️` no_tech
- Score, título, budget, complexidade, horas estimadas
- Justificativa, rascunho de proposta (code block), red flags, link da vaga

Campos vindos do usuário/IA (título, justificativa, red flags) passam por
`escape_md` para escapar `_ * ` [`. Se mesmo assim o Telegram responder 400 com
erro de parse, a mensagem é reenviada em texto puro como fallback.

## Perfil do usuário (config.py::PROFILE_SUMMARY)

Python developer, data scientist, experienced manager. Expert em dashboards
(Streamlit/Plotly), data pipelines, Python automation, music data (Spotify API),
sports analytics. Também atua como músico e produtor musical (beat-making,
mix/mastering, gravação remota de instrumento). Conta nova no Freelancer
(sem reviews). Foco em jobs de baixa competição.
