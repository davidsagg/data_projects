# upwork_jobs — Claude Code Project Brief

> Drop este arquivo como `CLAUDE.md` na raiz de `data_projects/upwork_jobs/`.
> Nota de portfólio: esta é a versão "Upwork" do agente de monitoramento de vagas;
> o projeto local `job_scout` é a evolução voltada ao Freelancer.com. Mantido aqui como referência.

## CLAUDE.md

Agente de monitoramento de oportunidades no Upwork via RSS, com scoring por IA e notificações via Telegram. Parte do repositório `data_projects`.

### Objetivo

Monitorar feeds RSS do Upwork, classificar oportunidades por relevância/concorrência, gerar rascunhos de proposta e notificar via Telegram para revisão humana em <5 min.

### Stack

- Python 3.11+
- SQLite (via sqlite3 nativo) para persistência
- anthropic SDK para scoring e geração de propostas
- feedparser para RSS
- httpx para requisições
- APScheduler para agendamento
- python-telegram-bot para notificações

### Estrutura do Projeto

```
upwork_jobs/
├── CLAUDE.md               ← este arquivo
├── .env.example            ← variáveis necessárias
├── requirements.txt
├── main.py                 ← entry point (scheduler + orquestrador)
├── config.py               ← carrega .env e constantes
├── database.py             ← SQLite: jobs vistos, propostas geradas
├── rss_fetcher.py          ← busca e parseia feeds RSS do Upwork
├── job_scorer.py           ← Claude API: avalia oportunidade (score 0-10)
├── proposal_generator.py   ← Claude API: gera rascunho de proposta
├── telegram_notifier.py    ← envia notificação formatada ao Telegram
└── feeds.yaml              ← configuração dos feeds por nicho
```

### Fluxo Principal

1. Scheduler aciona `main.py` a cada 30 min
2. `rss_fetcher` busca todos os feeds em `feeds.yaml`
3. Filtra jobs já vistos (database) e que atendam filtros básicos
4. `job_scorer` avalia cada job novo (score 0-10) via Claude
5. Jobs com score >= 7 → `proposal_generator` cria rascunho
6. `telegram_notifier` envia card formatado com score + proposta
7. Job salvo no banco com status "notified"

### Regras de Negócio

- Apenas jobs com budget declarado entre $50 e $500
- Apenas jobs com < 10 proposals (campo no RSS quando disponível)
- Nichos alvo: dados/dashboards, música, esportes, automações Python
- Nunca reprocessar o mesmo `job_id`
- Score < 7: salva no banco como "low_score", não notifica

### Como Rodar

```bash
pip install -r requirements.txt
cp .env.example .env    # preencher as variáveis
python main.py          # roda uma vez imediatamente + agenda loop
```

## Arquivo: `.env.example`

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Telegram
TELEGRAM_BOT_TOKEN=...         # BotFather token
TELEGRAM_CHAT_ID=...           # seu chat_id pessoal

# Configurações do agente
SCORE_THRESHOLD=7              # score mínimo para notificar
BUDGET_MIN=50                  # USD
BUDGET_MAX=500                 # USD
CHECK_INTERVAL_MINUTES=30      # frequência do scheduler
```

## Arquivo: `requirements.txt`

```
anthropic>=0.25.0
feedparser>=6.0.11
httpx>=0.27.0
apscheduler>=3.10.4
python-telegram-bot>=21.0
python-dotenv>=1.0.0
pyyaml>=6.0.1
```

## Arquivo: `feeds.yaml`

```yaml
# Feeds RSS do Upwork por nicho
# URL base: https://www.upwork.com/ab/feed/jobs/rss?q=TERMO&sort=recency
# Não requer autenticação. Limite: ~50 jobs por feed.

feeds:
  dados_dashboards:
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=dashboard+python&sort=recency&budget=50-500"
      label: "Dashboard Python"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=streamlit+dashboard&sort=recency"
      label: "Streamlit"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=data+visualization+plotly&sort=recency"
      label: "Plotly Visualization"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=python+automation+script&sort=recency&budget=50-300"
      label: "Python Automation"
  musica:
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=spotify+api+python&sort=recency"
      label: "Spotify API"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=music+data+analysis&sort=recency"
      label: "Music Data"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=music+automation+python&sort=recency"
      label: "Music Automation"
  esportes:
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=sports+analytics+python&sort=recency"
      label: "Sports Analytics"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=sports+data+dashboard&sort=recency"
      label: "Sports Dashboard"
    - url: "https://www.upwork.com/ab/feed/jobs/rss?q=football+soccer+statistics+scraping&sort=recency"
      label: "Football Stats"
```

## Arquivo: `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Regras de negócio
SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", 7))
BUDGET_MIN = int(os.getenv("BUDGET_MIN", 50))
BUDGET_MAX = int(os.getenv("BUDGET_MAX", 500))
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 30))

# Paths
DB_PATH = "upwork_jobs.db"
FEEDS_PATH = "feeds.yaml"

# Claude model
CLAUDE_MODEL = "claude-opus-4-5"
```

## Arquivo: `database.py`

```python
import sqlite3
from config import DB_PATH

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                budget TEXT,
                description TEXT,
                feed_label TEXT,
                score INTEGER,
                proposal_draft TEXT,
                status TEXT,          -- 'notified', 'low_score', 'filtered'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_seen(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return row is not None

def save_job(job: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO jobs
            (job_id, title, url, budget, description, feed_label, score, proposal_draft, status)
            VALUES (:job_id, :title, :url, :budget, :description, :feed_label,
                    :score, :proposal_draft, :status)
        """, job)
        conn.commit()
```

## Arquivo: `rss_fetcher.py`

```python
import feedparser
import hashlib
import re
import yaml
from config import FEEDS_PATH, BUDGET_MIN, BUDGET_MAX

def load_feeds() -> list[dict]:
    with open(FEEDS_PATH) as f:
        data = yaml.safe_load(f)
    feeds = []
    for niche, items in data["feeds"].items():
        for item in items:
            feeds.append({"niche": niche, **item})
    return feeds

def extract_budget(text: str) -> float | None:
    """Tenta extrair budget numérico do título ou descrição."""
    patterns = [
        r'\$([0-9,]+)',
        r'USD\s*([0-9,]+)',
        r'budget[:\s]+\$?([0-9,]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", ""))
            return value
    return None

def make_job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def fetch_all_jobs() -> list[dict]:
    feeds = load_feeds()
    all_jobs = []
    for feed_config in feeds:
        parsed = feedparser.parse(feed_config["url"])
        for entry in parsed.entries:
            job_id = make_job_id(entry.get("link", entry.get("id", "")))
            title = entry.get("title", "")
            description = entry.get("summary", "")
            url = entry.get("link", "")
            # Filtro de budget básico
            budget_text = title + " " + description
            budget_value = extract_budget(budget_text)
            if budget_value is not None:
                if not (BUDGET_MIN <= budget_value <= BUDGET_MAX):
                    continue
            all_jobs.append({
                "job_id": job_id,
                "title": title,
                "description": description[:2000],  # limita para Claude
                "url": url,
                "budget": str(budget_value) if budget_value else "not specified",
                "feed_label": feed_config["label"],
                "niche": feed_config["niche"],
            })
    return all_jobs
```

## Arquivo: `job_scorer.py`

```python
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SCORER_SYSTEM = """
Você é um avaliador de oportunidades freelance para um desenvolvedor Python sênior
especializado em dashboards, automações de dados, análise de dados musicais e esportivos.
O desenvolvedor tem conta nova no Upwork (sem reviews ainda) e busca projetos de baixa
complexidade e baixa concorrência para construir reputação.

Avalie o job e retorne APENAS um JSON válido com esta estrutura:
{
  "score": <inteiro de 0 a 10>,
  "justification": "<2 frases explicando o score>",
  "complexity": "<low|medium|high>",
  "estimated_hours": <número>,
  "red_flags": ["<lista de alertas ou array vazio>"]
}

Critérios de score alto (7-10):
- Descrição vaga ou confusa (cliente sem maturidade técnica)
- Budget compatível com a complexidade
- Poucos proposals esperados (job recente, nicho específico)
- Solúvel com Python, pandas, Streamlit, Plotly, APIs públicas
- Cliente parece precisar mais de orientação do que de código complexo

Critérios de score baixo (0-6):
- Alta especialização exigida (ML avançado, sistemas complexos)
- Budget irreal para o escopo
- Muita concorrência esperada (tópico genérico)
- Requer stack específica que não é Python/dados
"""

def score_job(job: dict) -> dict:
    prompt = f"""
Título: {job['title']}
Descrição: {job['description']}
Budget: {job['budget']}
Nicho: {job['niche']}
Feed: {job['feed_label']}

Avalie esta oportunidade.
"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        system=SCORER_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    import json
    text = response.content[0].text.strip()
    # Remove possíveis backticks
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)
```

## Arquivo: `proposal_generator.py`

```python
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROPOSAL_SYSTEM = """
Você escreve propostas de freelance no Upwork para um desenvolvedor Python experiente,
especialista em dados, dashboards e automações. A conta é nova (sem reviews).

Regras da proposta:
- Máximo 150 palavras
- Começa identificando o problema REAL do cliente (não copiando o título)
- Mostra que entendeu o que o cliente quer alcançar, não só o que pediu
- Menciona uma abordagem técnica concreta (ex: "usando Streamlit + Plotly")
- Termina com uma pergunta simples para engajar o cliente
- Tom: direto, confiante, humano — sem buzzwords nem exageros
- Idioma: inglês

Retorne APENAS a proposta em texto puro, sem explicações adicionais.
"""

def generate_proposal(job: dict, score_data: dict) -> str:
    prompt = f"""
Título do job: {job['title']}
Descrição: {job['description']}
Budget: {job['budget']}
Score de oportunidade: {score_data['score']}/10
Complexidade estimada: {score_data['complexity']}
Horas estimadas: {score_data['estimated_hours']}h

Escreva a proposta.
"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=PROPOSAL_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()
```

## Arquivo: `telegram_notifier.py`

```python
import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_job_notification(job: dict, score_data: dict, proposal: str):
    score = score_data["score"]
    complexity = score_data["complexity"]
    hours = score_data["estimated_hours"]
    flags = score_data.get("red_flags", [])

    # Emoji de score
    if score >= 9:
        emoji = "🔥"
    elif score >= 7:
        emoji = "✅"
    else:
        emoji = "⚠️"

    flags_text = "\n".join(f"  ⚠️ {f}" for f in flags) if flags else "  Nenhum"

    message = f"""
{emoji} *Score {score}/10* — {job['feed_label']}

*{job['title']}*

💰 Budget: ${job['budget']}
🧩 Complexidade: {complexity} (~{hours}h)

*Red Flags:*
{flags_text}

*Justificativa:*
_{score_data['justification']}_

*Rascunho de Proposta:*
{proposal}

🔗 [Ver no Upwork]({job['url']})
""".strip()

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = httpx.post(url, json=payload, timeout=10)
    resp.raise_for_status()
```

## Arquivo: `main.py`

```python
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from database import init_db, is_seen, save_job
from rss_fetcher import fetch_all_jobs
from job_scorer import score_job
from proposal_generator import generate_proposal
from telegram_notifier import send_job_notification
from config import SCORE_THRESHOLD, CHECK_INTERVAL_MINUTES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def run_pipeline():
    log.info("🔄 Iniciando pipeline de jobs...")
    jobs = fetch_all_jobs()
    log.info(f"📡 {len(jobs)} jobs encontrados nos feeds")
    new_jobs = [j for j in jobs if not is_seen(j["job_id"])]
    log.info(f"🆕 {len(new_jobs)} jobs novos para avaliar")

    for job in new_jobs:
        try:
            score_data = score_job(job)
            score = score_data["score"]
            log.info(f"Score {score}/10 — {job['title'][:60]}")
            if score >= SCORE_THRESHOLD:
                proposal = generate_proposal(job, score_data)
                send_job_notification(job, score_data, proposal)
                status = "notified"
                log.info(f"✅ Notificação enviada para: {job['title'][:60]}")
            else:
                proposal = ""
                status = "low_score"
            save_job({
                **job,
                "score": score,
                "proposal_draft": proposal,
                "status": status,
            })
        except Exception as e:
            log.error(f"Erro processando job {job['job_id']}: {e}")
            # Salva como visto para não reprocessar em loop
            save_job({**job, "score": 0, "proposal_draft": "", "status": "error"})

    log.info("✅ Pipeline concluído")

if __name__ == "__main__":
    init_db()
    log.info(f"🚀 Upwork Jobs Agent iniciado — verificando a cada {CHECK_INTERVAL_MINUTES} min")
    # Roda imediatamente na primeira execução
    run_pipeline()
    # Agenda execuções futuras
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="upwork_pipeline"
    )
    scheduler.start()
```

## Setup Rápido (rodar no terminal)

```bash
# 1. Criar estrutura
mkdir -p data_projects/upwork_jobs
cd data_projects/upwork_jobs

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis
cp .env.example .env
# editar .env com suas chaves

# 5. Testar
python main.py
```

## Como obter o `TELEGRAM_CHAT_ID`

1. Falar com @BotFather → criar bot → copiar token
2. Falar com @userinfobot → ele retorna seu chat_id
3. Colar ambos no .env

## Próximas evoluções (backlog)

| Prioridade | Feature |
|---|---|
| Alta | Comando /list no Telegram para ver últimos jobs |
| Alta | Botão inline "Marcar como enviado" no Telegram |
| Média | Dashboard Streamlit com histórico de jobs e conversões |
| Média | Ajuste automático de score_threshold por feedback |
| Baixa | Exportar proposals aceitas para treino/few-shot |
