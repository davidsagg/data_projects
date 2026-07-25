# SaggiCRM

CRM pessoal, 100% local, para organizar contatos exportados do LinkedIn — estilo
Dex/Clay: grupos, filtros por empresa/cargo/cidade, mapa e histórico de
relacionamento (notas + lembretes de follow-up). Sem autenticação — feito para
rodar só na sua máquina.

*A personal, fully-local CRM for organizing LinkedIn contacts — Dex/Clay-style
groups, filters, a map view, and relationship history (notes + follow-up
reminders). No authentication — designed to run only on your machine.*

## Stack

- **Backend**: FastAPI, SQLAlchemy 2.0, Alembic, SQLite, httpx (geocodificação via
  Nominatim/OpenStreetMap).
- **Frontend**: React + TypeScript, Vite, Tailwind CSS, Zustand, react-leaflet.

## Setup

```bash
make setup   # cria venv + instala deps + roda migrations
make dev     # backend (porta 8007) + frontend (porta 5177) em paralelo
```

Depois abra `http://localhost:5177`, vá em **Importar** e envie o `Connections.csv`
exportado do LinkedIn (`linkedin.com/psettings/member-data` → "Get a copy of your
data" → "Connections").

## Uso

1. **Importar** — envie o CSV de conexões do LinkedIn. Reimportar depois (ex.:
   novo export) só atualiza empresa/cargo/email — nunca sobrescreve cidade, grupos,
   notas ou lembretes que você já preencheu.
2. **Contatos** — busque, filtre por empresa/cargo/cidade/grupo, edite qualquer
   campo inline, registre notas de interação e lembretes de follow-up.
3. **Grupos** — organize contatos em listas (ex. "Board Advisors", "Prospects").
   Seleção em massa na lista de contatos para atribuir grupo a vários de uma vez.
4. **Mapa** — o export do LinkedIn não traz localização por contato, só o nome da
   empresa. No perfil de um contato (ou em lote, na página de Importar/Mapa), use
   "sugerir cidade" para geocodificar a empresa via OpenStreetMap — sempre editável
   manualmente depois.
5. **Lembretes** — todos os follow-ups pendentes/atrasados/concluídos, de todos os
   contatos, num só lugar.

## Arquitetura

Ver `CLAUDE.md` para detalhes de estrutura, modelo de dados e endpoints.

## Privacidade

O export do LinkedIn e o banco de dados local contêm informações reais de
milhares de contatos — eles ficam de fora do Git (`.gitignore` da raiz do
monorepo). Só o código deste projeto é versionado.

## Status

Fase 1 completa: import do LinkedIn, CRUD de contatos/grupos/interações/lembretes,
geocodificação por empresa com cache, dashboard, mapa. Sincronização automática
com o LinkedIn fica para uma fase futura (o LinkedIn não oferece uma API pública
para isso — exigiria scraping, fora de escopo por ora).
