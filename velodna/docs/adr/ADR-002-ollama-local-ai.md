# ADR-002 — Ollama para inferência de IA local

**Status:** Aceito  
**Data:** 2026-04-26  
**Decisores:** Time VeloDNA

---

## Contexto

O módulo AI Coach precisa gerar insights pós-atividade, responder perguntas em linguagem natural e produzir planos de treino personalizados. O system prompt inclui dados sensíveis do atleta (peso, FC, métricas de saúde). As opções são:

1. **OpenAI / Anthropic API** — qualidade superior, mas dados trafegam para servidores externos, custo por token, dependência de internet e latência de rede.
2. **LM Studio** — GUI-first, sem API HTTP estável para integração programática.
3. **Ollama** — servidor HTTP local, modelos GGUF quantizados, API compatível com OpenAI, suporte a streaming, zero custo por inferência.

O requisito de privacidade é explícito: **dados de saúde e treino do atleta não devem sair do dispositivo local**.

---

## Decisão

Usar **Ollama** como runtime de inferência, acessível via `http://host.docker.internal:11434` a partir do DevContainer.

Modelos primário: `llama3:latest` (8B, Q4_0).  
Fallback: `mistral:latest` (7.2B, Q4_K_M).

---

## Consequências

**Positivas:**
- 100% local: dados de saúde nunca saem do dispositivo.
- Zero custo por inferência após download inicial dos modelos.
- API HTTP compatível com padrão OpenAI — possível migração para API externa com mudança mínima de código.
- Streaming nativo via `/api/chat`.
- Modelos já disponíveis no ambiente (confirmado na Fase 1).

**Negativas / Riscos:**
- Qualidade de raciocínio inferior a GPT-4 / Claude para prompts complexos. Mitigação: system prompt estruturado com dados contextuais ricos; respostas limitadas a 250 palavras para reduzir drift.
- Latência de primeira inferência em hardware sem GPU pode ser 5–30 s. Mitigação: background task para insights pós-atividade; streaming para chat.
- Modelos não fine-tuned em ciclismo. Mitigação: few-shot examples no system prompt com terminologia específica (TSS, FTP, CTL).
