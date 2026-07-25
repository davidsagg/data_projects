# saggicrm

CRM pessoal local para organizar contatos exportados do LinkedIn (estilo Dex/Clay):
grupos, filtros por empresa/cargo/cidade, mapa, histórico de interações e lembretes
de follow-up. Sem autenticação — uso local, single-user.

Stack: FastAPI + SQLAlchemy 2.0 + Alembic + SQLite (backend) · React + TypeScript +
Vite + Tailwind + Zustand + react-leaflet (frontend).

## Privacidade — importante

O export do LinkedIn (`Basic_LinkedInDataExport_*.zip/`) e o banco (`data/*.db`)
contêm dados reais de milhares de contatos de terceiros (nome, email, cargo, empresa).
Ambos estão no `.gitignore` da raiz do monorepo — **nunca versionar**. Só o código vai
para o Git.

## Portas

API `8007` · Frontend `5177` (proxy `/api` → API). Ver `.env.example`.

## Comandos

```
make setup   # cria venv + instala deps (backend e frontend) + roda migrations
make dev     # backend (--reload) + frontend em paralelo
make test    # pytest do backend
```

Sem Makefile: `cd backend && source .venv/bin/activate && SAGGICRM_DATA=../data
uvicorn main:app --reload --port 8007` e `cd frontend && npm run dev`.

## Estrutura

```
saggicrm/
├── backend/
│   ├── main.py                FastAPI(), CORS, routers, /health
│   ├── src/
│   │   ├── api/                contacts, groups, interactions, reminders, geocode, importer, stats
│   │   ├── models/             models.py (SQLAlchemy) · schemas.py (Pydantic)
│   │   ├── db/database.py      engine/SessionLocal/Base/get_db — SQLITE_PATH via SAGGICRM_DATA
│   │   └── services/           linkedin_import.py · geocode.py (Nominatim + cache)
│   ├── alembic/                migrations
│   └── tests/                  pytest (import, contacts, reminders, geocode cache)
├── frontend/
│   └── src/{pages,components,api,store,types,lib}
├── data/                        saggicrm.db (gitignored)
└── Basic_LinkedInDataExport_*.zip/  export bruto do LinkedIn (gitignored)
```

## Modelo de dados

- **Contact**: nome, `linkedin_url` (único quando presente), email, empresa, cargo,
  `connected_on`, `city`/`country`/`lat`/`lon`, `source` (`linkedin_import`|`manual`).
  Campos vindos do LinkedIn são atualizados a cada reimport; `city`, grupos, notas e
  lembretes são curados pelo usuário e **nunca sobrescritos** pelo import.
- **Group**: N:N com Contact (tabela `contact_group`).
- **Interaction**: histórico de relacionamento (nota/ligação/reunião/email/café/outro).
- **Reminder**: follow-up com `due_date`, `is_done`.
- **CompanyGeocodeCache**: cache por empresa (normalizada) para não re-geocodificar e
  respeitar o rate limit do Nominatim (1 req/s). Resultado negativo também é cacheado.
- "Último contato" não é coluna — é `MAX(Interaction.occurred_at)` calculado na query.

## Import do LinkedIn (`POST /api/import/linkedin`)

Parseia `Connections.csv` (pula o preâmbulo "Notes:" até achar o header `First Name`).
Linhas com nome E sobrenome vazios são "contas fantasma" do export e são puladas
(`skipped_blank`). Upsert por `linkedin_url`; se vazio, fallback por
nome+sobrenome+empresa (case-insensitive). Reimportar é seguro — nunca sobrescreve
campos curados pelo usuário.

## Geocodificação (`POST /api/geocode/company` e `/api/geocode/bulk`)

O export do LinkedIn não traz localização por contato — só nome da empresa. A
sugestão de cidade geocodifica o **nome da empresa** via Nominatim/OpenStreetMap
(gratuito, sem API key, granularidade de cidade). `/bulk` processa em lotes pequenos
(`chunk_size`, default 15) com throttle de 1.1s entre chamadas novas; o frontend
chama em loop até `remaining == 0`. Cache por empresa em `CompanyGeocodeCache` evita
re-geocodificar contatos que compartilham empregador.

## Frontend

Sem React Query — fetch direto via Axios (`src/api/client.ts`) + `useEffect`/estado
local por página. Zustand (`src/store/filters.ts`) só para o estado de filtros da
lista de contatos. Mapa: `react-leaflet` + `CircleMarker` agrupado por cidade
(clustering "manual" via agregação no cliente, sem `leaflet.markercluster`).

`react-router-dom` fixado em `7.11.0`: `npm audit` aponta CVEs de React Router que
são todos específicos de SSR/RSC/server actions — não se aplicam aqui (SPA
client-side puro, sem SSR, sem auth). Risco aceito.
