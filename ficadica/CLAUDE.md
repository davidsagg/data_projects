# Fica a Dica Premium — Scraper & Plano de Estudos

## Contexto do Projeto

Este projeto automatiza o mapeamento completo do site **Fica a Dica Premium**, plataforma de cursos de guitarra/violão com conteúdo protegido por login (WordPress + WooCommerce + plugin WPLMS).

**Objetivos:**
1. Fazer scraping autenticado de todos os cursos, módulos e aulas disponíveis
2. Persistir os dados em JSON e CSV
3. Gerar um plano de estudos personalizado com base no catálogo mapeado
4. Exibir tudo em uma interface web local

## Status do Projeto

| Módulo | Status |
|--------|--------|
| Autenticação WordPress (`auth.py`) | Implementado |
| Crawler Playwright (`crawler.py`) | Implementado |
| Parser e categorização (`parser.py` + `exporter.py`) | Implementado |
| Gerador de plano de estudos (`planner.py`) | Implementado |
| Relatórios JSON/Markdown/Rich (`report_generator.py`) | Implementado |
| Dashboard web local (`dashboard/`) | Implementado |
| Catálogo mapeado (`data/courses.json`) | Gerado (25 cursos) |
| Plano de estudos (`data/study_plan.json`) | Gerado |

## Arquitetura do Projeto

```
ficadica/
├── CLAUDE.md                        ← este arquivo
├── .env.example                     ← template de credenciais
├── .gitignore
├── requirements.txt
├── check_env.py                     ← verifica configuração do ambiente
├── run_scraper.py                   ← entry point: crawla todos os cursos
├── run_parser.py                    ← entry point: normaliza → JSON/CSV/Markdown
├── run_planner.py                   ← entry point: gera plano de estudos
├── start_dashboard.sh               ← inicia servidor em http://localhost:8766
├── scraper/
│   ├── auth.py                      ← login WordPress + gerenciamento de sessão
│   ├── config.py                    ← configuração via .env
│   ├── crawler.py                   ← crawler principal (Playwright, seletores WPLMS)
│   ├── parser.py                    ← inferência de categoria, nível, estilo, prioridade
│   └── exporter.py                  ← exportação JSON / CSV / Markdown
├── study_plan/
│   ├── planner.py                   ← lógica de geração do plano (4 fases, 24 semanas)
│   ├── report_generator.py          ← relatório em JSON / Markdown / Rich terminal
│   └── user_profile.json            ← perfil do usuário (Dave, Jazz/MPB)
├── dashboard/
│   ├── index.html                   ← UI completa (dark theme, estilos inline)
│   ├── app.js                       ← lógica JavaScript
│   └── server.py                    ← servidor HTTP local (porta 8766, APIs REST)
└── data/                            ← arquivos gerados (não commitados: raw/, session.json)
    ├── courses_raw.json             ← checkpoint do crawler
    ├── courses.json                 ← catálogo normalizado
    ├── courses.csv                  ← formato flat para análise
    ├── catalog.md                   ← catálogo legível por humanos
    ├── study_plan.json              ← plano de estudos gerado
    └── study_plan.md                ← plano de estudos em Markdown
```

## Estrutura do Site

- **Plataforma:** WordPress + WooCommerce + **WPLMS** (identificado via inspeção do HTML)
- **URL base dos cursos:** `https://www.ficaadicapremium.com.br/course/{slug}/`
- **Autenticação:** `/wp-login.php` com campos `#user_login` e `#user_pass`

### Seletores WPLMS (Crawler)
- Seções: `li.course_section` → `label` (título)
- Aulas: `li.course_lesson` → `span.item_title` (título), `span.time` (duração)
- Instrutor: `a.course_instructor`
- Título: `h1.course_element_text`

### 7 Pilares de Conteúdo
1. Técnica Instrumental
2. Harmonia
3. Improvisação
4. Escalas
5. Ritmo / Levadas
6. Repertório / Músicas
7. Leitura Musical

### Equipe
- **Coordenador pedagógico:** Nelson Faria
- **Professores:** Nelson Faria, Alexandre Carvalho, Débora Gurgel, Michel Caramelo, e outros

## Perfil do Usuário (Dave — `study_plan/user_profile.json`)

- Guitarrista intermediário-avançado
- Toca Jazz e MPB em banda
- Guitarra principal: Fender Strat + Hollowbody (jazz)
- Interesse principal: Jazz, improvisação, harmonia avançada, MPB, Bossa Nova, Blues
- Objetivo: aprimoramento, não iniciação
- Disponibilidade: 5h/semana, sessões de 45 min

## Plano de Estudos (4 Fases / 24 Semanas)

| Fase | Semanas | Foco |
|------|---------|------|
| 1 — Fundamentos Avançados | 1–6 | Harmonia + Escalas |
| 2 — Linguagem e Improvisação | 7–14 | Improvisação + Fraseologia Jazz/MPB |
| 3 — Repertório e Aplicação | 15–20 | Repertório + Standards + Chord Melody |
| 4 — Aprofundamento e Estilo | 21–24 | Jazz Avançado + Modal + Estilo Próprio |

## Fluxo de Execução

```bash
# 1. Verificar ambiente
python check_env.py

# 2. Crawlar o site (autenticado, Playwright)
python run_scraper.py [--resume] [--headless] [--course SLUG]

# 3. Normalizar e exportar
python run_parser.py

# 4. Gerar plano de estudos
python run_planner.py [--weeks 24] [--profile study_plan/user_profile.json]

# 5. Iniciar dashboard
bash start_dashboard.sh
# → http://localhost:8766
```

## APIs do Dashboard

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/courses` | GET | Catálogo completo |
| `/api/study_plan` | GET | Plano de estudos |
| `/api/profile` | GET/POST | Perfil do usuário |
| `/api/regenerate` | POST | Regenera plano de estudos |
| `/api/rescrape` | POST | Inicia novo scraping (background) |
| `/api/status/{job_id}` | GET | Status de job assíncrono |

## Stack Técnica

- **Scraping:** Python 3.12 + Playwright (autenticação, navegação, aguarda JS)
- **Parsing:** BeautifulSoup4 + lxml
- **Dados:** JSON + CSV
- **Dashboard:** HTML/CSS/JS puro (sem framework, servidor Python stdlib)
- **UI:** Rich (terminal), dark theme inspirado em Linear/Vercel
- **Credenciais:** via arquivo `.env` (nunca comitar)

## Notas Importantes

- O site usa **WPLMS** (não LearnDash como inicialmente suspeitado) — seletores específicos implementados
- Sessão salva em `data/session.json` para evitar re-login (excluído do git)
- HTML bruto salvo em `data/raw/` por curso para reprocessamento sem novo crawl (excluído do git)
- Checkpoint automático a cada 5 cursos em `data/courses_raw.json`
- Dashboard serve na porta **8766** (não 8765)
