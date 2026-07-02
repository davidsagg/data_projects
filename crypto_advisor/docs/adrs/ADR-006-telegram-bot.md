# ADR-006: Telegram Bot para entrega do relatório semanal

**Status:** Aceito  
**Data:** 2026-05-12  
**Autores:** David Saggioro

---

## Contexto

O relatório semanal de recomendações precisa ser entregue todo **domingo às 18h** de forma confiável, com suporte a formatação rica (markdown, tabelas), e deve redirecionar o usuário para a UI de validação (Streamlit) para aprovação/rejeição das recomendações.

Alternativas consideradas: e-mail (Gmail API), WhatsApp (API paga/instável), Slack (overkill para uso pessoal), notificação local macOS.

---

## Decisão

Usar **Telegram Bot** via `python-telegram-bot >= 21.0` para entrega do relatório semanal e alertas do Tax Optimizer.

---

## Racional

| Critério                   | Telegram Bot | Gmail API   | Slack      |
|----------------------------|--------------|-------------|------------|
| Custo                      | Zero         | Zero        | Free tier  |
| Latência de entrega        | Instantânea  | ~1-5 min    | Instantânea|
| Suporte a Markdown/HTML    | Sim (HTML)   | Sim         | Sim (mrkdwn)|
| Notificação push mobile    | Sim          | Depende app | Sim        |
| Configuração               | Simples      | OAuth2 flow | Workspace  |
| Envio programático Python  | `python-telegram-bot` | `google-api-python-client` | `slack-sdk` |

O Telegram é gratuito, confiável, suporta HTML com formatação rica, e `python-telegram-bot` é a biblioteca mais madura do ecossistema.

---

## Mensagens implementadas

### 1. Relatório semanal (domingo 18h)
```
📊 CryptoAdvisor — Relatório Semanal (12/05/2026)

💰 Portfólio: R$8.420,50 | +12,3% esta semana

🎯 Recomendações (3):
  ▸ BTC — COMPRAR | Entry: $65.000 | Stop: $62.000 | Alvo: $71.000 | RR: 2,0x
  ▸ ETH — MANTER
  ▸ SOL — VENDER | Impacto fiscal: +R$1.200 (dentro do limite)

🧾 Status fiscal: R$12.400 / R$35.000 (35%) ✅ SAFE

👉 Acesse a UI para aprovar: http://localhost:8501
```

### 2. Alertas do Tax Optimizer
- WARNING: quando acumulado ultrapassa R$28.000
- CRITICAL: quando acumulado ultrapassa R$33.000
- BLOCKED: quando limite de R$35.000 é atingido

---

## Implementação

```python
# Envio assíncrono para não bloquear o scheduler
await bot.send_message(
    chat_id=TELEGRAM_CHAT_ID,
    text=report_html,
    parse_mode=ParseMode.HTML,
)
```

---

## Consequências

- **Positivas:** Entrega instantânea, mobile-friendly, zero custo, fácil configuração (BotFather)
- **Negativas:** Requer conta Telegram pessoal; chat_id precisa ser obtido manualmente uma vez
- **Setup:** `BotFather → /newbot → salvar token → enviar /start → GET /getUpdates para obter chat_id`
- **Mitigações:** Fallback para log local caso Telegram esteja inacessível; o relatório HTML completo sempre salvo em `data/reports/`
