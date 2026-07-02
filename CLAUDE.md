# Data Projects — Portfólio "Build To Learn"

> Configuração-mãe desta pasta. Cada subpasta é um projeto independente,
> construído no estilo **Build To Learn** para compor o portfólio do Dave
> (Gerente de Projetos/Programas, Cientista de Dados, co-founder de consultoria).
> Última atualização: 2026-06-30.

## Objetivo desta pasta

Para **cada projeto** o ciclo de vida é:

1. **Construir** localmente (Build To Learn).
2. **Publicar no GitHub** (monorepo único `davidsagg/data_projects`, conta `davidsagg`).
3. **Documentar**: gerar/atualizar o `README.md` do GitHub e um **post para o Substack**.
4. **Sincronizar com o Google Drive**: a pasta `data_projects` do Drive contém as
   documentações de fase de cada projeto. Origem da verdade da documentação narrativa = Drive;
   origem da verdade do código = esta pasta local + GitHub.

## Convenções

- **Monorepo único**: `github.com/davidsagg/data_projects` — cada projeto é uma subpasta.
  Histórico achatado em 2026-07-02 (os `.git` por projeto foram removidos; backups completos
  em `_git_history_backup/`, que é ignorado pelo git).
- Conta GitHub: **`davidsagg`**.
- Documentação sincronizada do Drive fica em **`<projeto>/docs/`** (mantendo o nome original).
- `CLAUDE.md` por projeto = instruções de contexto para o agente naquele projeto.
- `.env` nunca versionado; usar `.env.example`.
- Idioma da documentação: PT-BR (exceto README público, que pode ser bilíngue/EN).

## Inventário dos projetos

| Projeto local | Descrição curta | README | CLAUDE.md | .git local | GitHub | Pasta no Drive |
|---|---|---|---|---|---|---|
| `bandkit` | Web app de gestão de shows/setlists para bandas (PWA, ChordPro) | ✅ | — | ✅ | ❌ | `BandKit` (8 docs) |
| `crypto_advisor` | Agente de recomendação semanal de cripto p/ swing trade + tax optimization IR | — | ✅ | ✅ | ❌ | — |
| `ficadica` | Scraper autenticado + plano de estudos do "Fica a Dica Premium" | — | ✅ | ❌ | ❌ | `ficadica` (8 docs) |
| `job_scout` | Monitor de vagas (Freelancer.com via RSS) com scoring Claude + Telegram | ✅ | ✅ | ✅ | ❌ | `upwork-jobs` (2 docs) |
| `musicdna-ai` | Análise de áudio com embeddings, licenciamento e jam sessions (7 fases, TDD) | — | ✅ | ✅ | ❌ | `MusicDNA` (9 .docx) |
| `Preditiva` | Cases de ML/estatística (Diabetes, Turnover RH, VaR) em notebooks | — | — | ❌ | ❌ | — |
| `saggirag` | Chat com RAG sobre finanças usando Mistral 7B | ✅ | — | ❌ | ❌ | — |
| `special_gear` | Monitor de leilões da Receita Federal p/ instrumentos/áudio | ✅ | — | ❌ | ❌ | — |
| `trend-radar` | Plataforma de tendências do mercado musical BR (Airflow, dbt/DuckDB, ML, LLM) | ✅ | ✅ | ✅ | ❌ | `TrendRadar` (8 docs) |
| `velodna` | Plataforma de performance no ciclismo | ✅ | ✅ | ✅ | ❌ | `VeloDNA` (10 docs) |
| `work_in_progress` | Scripts/modelos em desenvolvimento (incubadora) | ✅ | — | ✅ | ✅ `davidsagg/work_in_progress` | — |

Pastas do Drive **sem** projeto local correspondente: `MacroFactor Setup` (setup pessoal de
ciclismo — não é projeto de portfólio).

ID da pasta raiz no Drive: `1rPop5kgU0vxrp_lF0Jk1x_nU8DOwSinn`.

## Workflow por projeto

### Publicar no GitHub (monorepo)
1. Garantir `.gitignore` e `.env.example` adequados; nunca commitar segredos (`.env`).
2. Trabalhar na raiz `data_projects` (origin = `davidsagg/data_projects`).
3. Commit + push da branch `main`. Cada projeto é uma subpasta, sem `.git` próprio.

### Gerar documentação
- **README (GitHub)**: objetivo, stack, setup, uso, arquitetura, status. Bilíngue quando fizer sentido.
- **Post Substack**: narrativa "o que aprendi construindo", baseada nos docs de fase do Drive
  (`<projeto>/docs/`) — problema, decisões, trade-offs, resultado, próximos passos.
  **Sempre em 2 idiomas** (Dave publica EN + PT): `substack_<projeto>_EN.md` e `substack_<projeto>_PT.md`
  em `<projeto>/docs/`. Modelo/estilo: série "David Saggioro — Case Studies" (ex.: post de VaR),
  com marcadores `📷 [Image/Imagem: ...]` onde entram screenshots.

### Sincronizar com o Drive
- Direção padrão: **Drive → Local** (documentação narrativa entra em `<projeto>/docs/`).
- Google Docs são exportados como `.md`; arquivos `.docx` nativos são copiados como `.docx`.

## Status do sync Drive → Local (atualizado 2026-06-30)

| Projeto | Pasta Drive | Docs | Status |
|---|---|---|---|
| `ficadica` | ficadica | 8 | ✅ Sincronizado (markdown limpo) em `ficadica/docs/` |
| `job_scout` | upwork-jobs | 2 | ⚠️ Parcial — brief atual sincronizado (`upwork_jobs_claudecode.md`); v1 (40 KB, rascunho redundante) **omitido por decisão** |
| `bandkit` | BandKit | 8 | 🔄 Em andamento — `00_project_charter.md` feito; fases 1-7 pendentes (só existem como Google Docs) |
| `velodna` | VeloDNA | 10 | ⏳ Pendente — download manual trouxe só atalhos `.gdoc` (sem conteúdo). Requer export Markdown/Word |
| `trend-radar` | TrendRadar | 8 | ⏳ Pendente — idem velodna (só `.gdoc`) |
| `musicdna-ai` | MusicDNA | 9 (.docx) | ✅ Sincronizado — 9 `.docx` + `project_charter.docx` (cópias fiéis) em `musicdna-ai/docs/` |

**Aprendizado importante (mecanismo de sync):** baixar do Drive passa todo o conteúdo pela
sessão do agente. Os docs de "fase" (BandKit/VeloDNA/TrendRadar) são Google Docs pesados em
tabelas e diagramas ASCII — a conversão para markdown limpo é cara e precisa de reconstrução
manual. Recomenda-se finalizar o lote restante via **rotina agendada** (uma leva de docs por
execução, contexto novo a cada run) em vez de tudo numa única sessão.

## Pendências / decisões em aberto

- ~~**Repos aninhados**~~ **RESOLVIDO (2026-07-02)**: migração para monorepo. Todos os `.git`
  internos foram removidos (backups em `_git_history_backup/`) e a raiz virou repo único
  apontando para `davidsagg/data_projects`. Reorganização física das pastas (aninhar tudo sob
  uma `data_projects/`) ficou para depois, por decisão do Dave.
- **Mapeamento `job_scout` ↔ `upwork-jobs`**: confirmar se é o mesmo projeto (Freelancer vs Upwork).
- Projetos sem `.git`: `ficadica`, `Preditiva`, `saggirag`, `special_gear` — inicializar quando publicar.
- Projetos sem pasta no Drive: `crypto_advisor`, `Preditiva`, `saggirag`, `special_gear`,
  `work_in_progress` — criar quando houver documentação narrativa.
