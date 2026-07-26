# saggicrm

CRM pessoal local para organizar contatos exportados do LinkedIn (estilo Dex/Clay):
grupos, filtros por empresa/setor/cargo/senioridade/cidade, favoritos, mapa,
histórico de interações e lembretes de follow-up. Sem autenticação — uso local,
single-user.

Stack: FastAPI + SQLAlchemy 2.0 + Alembic + SQLite (backend) · React + TypeScript +
Vite + Tailwind + Zustand + react-leaflet (frontend).

## Privacidade — importante

O export do LinkedIn e o banco (`data/*.db`) contêm dados reais de milhares de
contatos de terceiros (nome, email, cargo, empresa). O usuário reorganiza esses
exports livremente fora do controle do agente (ex.: moveu para `Files/` e adicionou
um export "Complete" em 2026-07-25) — por isso o `.gitignore` da raiz usa padrões
`saggicrm/**/*LinkedInDataExport*/` e `saggicrm/Files/` (não um caminho fixo) para
sobreviver a isso. **Nunca versionar dados** — só o código vai para o Git. Ao mexer
no `.gitignore`, sempre confirmar com `git check-ignore -v` antes de qualquer `git add`.

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
└── Files/ (ou pasta equivalente)  exports brutos do LinkedIn (gitignored)
```

## Modelo de dados

- **Contact**: nome, `linkedin_url` (único quando presente), email, empresa (texto
  livre, como veio do LinkedIn), `company_id` (FK p/ Company), cargo, `seniority`
  (calculado, ver abaixo), `is_favorite`, `connected_on`, `city`/`country`/`lat`/`lon`,
  `source` (`linkedin_import`|`manual`). Campos vindos do LinkedIn são atualizados a
  cada reimport; `city`, grupos, notas, lembretes e `is_favorite` são curados pelo
  usuário e **nunca sobrescritos** pelo import. `linkedin_url` é editável na tela de
  detalhe (a maioria dos contatos já vem com URL do próprio export, mas contatos
  criados manualmente não têm); colidir com a URL de outro contato retorna
  **409** com mensagem clara (`_commit_or_conflict` em `src/api/contacts.py`),
  em vez de estourar um 500 de `IntegrityError` na constraint `unique`.
- **Company**: `name` (canônico) + `normalized_name` (lowercase+trim, único) — resolve
  duplicatas de grafia (ex. "GE HealthCare" vs "GE Healthcare" viram uma só linha).
  `sector` é texto livre (lista sugerida em `frontend/src/lib/sectors.ts`), classificado
  via `get_or_create_company` (`src/services/companies.py`) no import/criação/edição.
  **Não** faz merge de nomes semanticamente diferentes (ex. "TRI CS Inc." vs "Peloton
  Consulting Group" continuam empresas separadas mesmo sendo o mesmo grupo real).
- **Seniority** (`src/services/seniority.py::classify_seniority`): regex por
  palavra-chave EN+PT sobre `position`, 6 níveis (C-Level/Fundador → Diretoria →
  Gerência → Especialista/Analista → Estagiário/Assistente → Não classificado),
  checados nessa ordem de prioridade. Cuidado com falsos-positivos já corrigidos:
  "Product/Service/System Owner" e "Business Partner" **não** contam como C-level
  (só "owner"/"partner" soltos contam) — ver `_NON_EXECUTIVE_OWNER_OR_PARTNER`.
- **Group**: N:N com Contact (tabela `contact_group`).
- **Interaction**: histórico de relacionamento (nota/ligação/reunião/email/café/outro).
- **Reminder**: follow-up com `due_date`, `is_done`.
- **CompanyGeocodeCache**: cache por empresa (normalizada) para não re-geocodificar e
  respeitar o rate limit do Nominatim (1 req/s). Resultado negativo também é cacheado.
- "Último contato" não é coluna — é `MAX(Interaction.occurred_at)` calculado na query.

**Setores**: cobertura em camadas — classificação manual das ~250 empresas com mais
contatos (conhecimento próprio, não uma API), heurística por palavra-chave no nome
para o resto (`hospital`→Saúde, `consultoria`→Consultoria etc.), e atribuição manual
em lote pela tela `/companies` (mesmo padrão de seleção múltipla da lista de
contatos). ~54% dos contatos tinham setor após a primeira passada — o resto fica
"sem setor" até o usuário taggear.

**Gotcha corrigido**: o endpoint `/api/geocode/bulk` originalmente reconsultava a
mesma leva de empresas para sempre quando elas falhavam na geocodificação (o
resultado negativo ficava em cache, mas a query de "empresas sem cidade" nunca
excluía quem já tinha sido tentado) — loop infinito real, já rodou 1,2M iterações
em produção antes de ser percebido. Corrigido excluindo do lote qualquer empresa já
presente em `CompanyGeocodeCache` (sucesso ou falha). Testes de regressão em
`tests/test_geocode_bulk.py`.

## Ordenação (`sort` + `sort_dir` em `/api/contacts` e `/api/companies`)

Cabeçalhos de coluna clicáveis (`frontend/src/components/SortableTh.tsx`), não um
dropdown — clicar de novo na mesma coluna alterna asc/desc; clicar numa coluna
diferente aplica a direção padrão dela (`DEFAULT_SORT_DIR` no frontend). Ícone ⇅
sempre visível nas colunas ordenáveis (mesmo inativas) para deixar claro que são
clicáveis — sem isso o usuário não percebia que dava pra ordenar.

Em contatos, `seniority` ordena pelo **rank real** (C-Level primeiro), não
alfabético, via `case()` sobre `SENIORITY_LEVELS` (`_SENIORITY_RANK` em
`src/api/contacts.py`). Contatos sem empresa/data de conexão (`company`,
`connected_on`) são sempre empurrados para o fim da lista (`nulls_last_fields`),
**independente da direção** — sem isso, ordenar por empresa mostrava só os
contatos com empresa em branco no topo (NULL é "menor valor" em SQL), o que
parecia "não fazer nada" à primeira vista.

Em empresas, sem essa proteção o "sem setor" ficaria embaralhado ao inverter a
direção; o key function usa um caractere alto (`"￿"`) no lugar de `None` para
manter "sem setor" sempre por último de forma simples.

## Import do LinkedIn (`POST /api/import/linkedin`)

Parseia `Connections.csv` (pula o preâmbulo "Notes:" até achar o header `First Name`).
Linhas com nome E sobrenome vazios são "contas fantasma" do export e são puladas
(`skipped_blank`). Upsert por `linkedin_url`; se vazio, fallback por
nome+sobrenome+empresa (case-insensitive). Reimportar é seguro — nunca sobrescreve
campos curados pelo usuário. `company_id` e `seniority` são recalculados a cada
criação/edição/import (`_apply_derived_fields` em `src/api/contacts.py`), nunca
ficam desatualizados.

## Geocodificação (`POST /api/geocode/company` e `/api/geocode/bulk`)

O export do LinkedIn não traz localização por contato — só nome da empresa. A
sugestão de cidade geocodifica o **nome da empresa** via Nominatim/OpenStreetMap
(gratuito, sem API key, granularidade de cidade). `/bulk` processa em lotes pequenos
(`chunk_size`, default 15) com throttle de 1.1s entre chamadas novas; o frontend
chama em loop até `remaining == 0`. Cache por empresa em `CompanyGeocodeCache` evita
re-geocodificar contatos que compartilham empregador.

## Frontend

Rotas: `/` (dashboard), `/contacts` + `/contacts/new` + `/contacts/:id`, `/groups`,
`/companies` + `/companies/:id` (lista com seleção em massa p/ setor + detalhe com
breakdown de senioridade), `/map`, `/reminders`, `/import`.

Sem React Query — fetch direto via Axios (`src/api/client.ts`) + `useEffect`/estado
local por página. Zustand (`src/store/filters.ts`) só para o estado de filtros da
lista de contatos (inclui `sort`/`sortDir` — ver seção de Ordenação). Dashboard usa
`filters.reset()` + `filters.setX()` + `navigate('/contacts')` para os cliques nos
gráficos caírem já filtrados; `/companies` usa query string (`?sector=`) em vez do
store, já que é uma tela própria sem filtro compartilhado com Contatos. Mapa:
`react-leaflet` + `CircleMarker` agrupado por cidade (clustering "manual" via
agregação no cliente, sem `leaflet.markercluster`).

`react-router-dom` fixado em `7.11.0`: `npm audit` aponta CVEs de React Router que
são todos específicos de SSR/RSC/server actions — não se aplicam aqui (SPA
client-side puro, sem SSR, sem auth). Risco aceito.
