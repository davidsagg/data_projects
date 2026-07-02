# job_scout

Agente one-shot que monitora vagas no **Freelancer.com** via RSS, pontua
oportunidades com **Claude API** e envia rascunhos de proposta no **Telegram**.

Fluxo: RSS → filtro de budget → scoring (Claude) → proposta (Claude) → Telegram.

## Setup

```bash
cp .env.example .env       # preencher chaves
pip install -r requirements.txt
python -c "from database import init_db; init_db()"
python main.py
```

Para execução recorrente, agende via cron / systemd timer externo
(o script roda one-shot e termina).

## Variáveis de ambiente

| Variável            | Padrão | Descrição                          |
|---------------------|--------|------------------------------------|
| `ANTHROPIC_API_KEY` | —      | Chave da API Anthropic             |
| `TELEGRAM_BOT_TOKEN`| —      | Token do bot Telegram              |
| `TELEGRAM_CHAT_ID`  | —      | ID do chat para notificações       |
| `SCORE_THRESHOLD`   | 7      | Score mínimo para notificar        |
| `BUDGET_MIN`        | 50     | Budget mínimo em USD (fixed-price) |
| `BUDGET_MAX`        | 500    | Budget máximo em USD (fixed-price) |

## Filtros aplicados ao RSS

- Hourly jobs são descartados (`/hr`, `/hour`, `per hour`, `hourly`).
- Jobs sem budget detectado no summary são descartados.
- Apenas jobs com budget em `[BUDGET_MIN, BUDGET_MAX]` passam.

## Status no SQLite

| Status          | Significado                                              |
|-----------------|----------------------------------------------------------|
| `notified`      | Score ≥ threshold e enviado ao Telegram com sucesso      |
| `notify_failed` | Score ≥ threshold mas o envio ao Telegram falhou         |
| `low_score`     | Score < threshold (não notificado)                       |
| `error`         | Erro inesperado no scoring/geração                       |

Veja `CLAUDE.md` para detalhes de arquitetura, scorer e perfil do usuário.
