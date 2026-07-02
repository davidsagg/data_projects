# Fica a Dica Premium — Scraper & Plano de Estudos

## Contexto do Projeto

Este projeto automatiza o mapeamento completo do site **Fica a Dica Premium** (<https://www.ficaadicapremium.com.br>), plataforma de cursos de guitarra/violão com conteúdo protegido por login (WooCommerce + SPA React).

O objetivo é:

1. Fazer scraping autenticado de todos os cursos, módulos e aulas disponíveis
2. Persistir os dados em JSON e CSV
3. Gerar um plano de estudos personalizado com base no catálogo mapeado
4. Exibir tudo em uma interface web local

## Arquitetura do Projeto

```
ficaadicapremium-scraper/
├── CLAUDE.md               ← este arquivo (contexto do projeto)
├── prompts/
│   ├── 01_setup.md         ← Prompt 1: configuração do ambiente
│   ├── 02_scraper.md       ← Prompt 2: scraper autenticado com Playwright
│   ├── 03_parser.md        ← Prompt 3: parser e estruturação dos dados
│   ├── 04_study_plan.md    ← Prompt 4: geração do plano de estudos
│   └── 05_dashboard.md     ← Prompt 5: dashboard web local
├── scraper/
│   ├── auth.py             ← módulo de autenticação
│   ├── crawler.py          ← crawler principal
│   ├── parser.py           ← extração e normalização
│   └── config.py           ← configurações (credenciais via .env)
├── data/
│   ├── raw/                ← HTML bruto das páginas
│   ├── courses.json        ← catálogo estruturado
│   └── study_plan.json     ← plano de estudos gerado
├── dashboard/
│   ├── index.html          ← interface web local
│   ├── app.js              ← lógica da interface
│   └── style.css           ← estilos
├── .env.example            ← template de credenciais
└── requirements.txt        ← dependências Python
```

## Estrutura Conhecida do Site

- **Plataforma:** WordPress + WooCommerce + plugin de cursos (provavelmente LearnDash ou similar)
- **SPA:** React no frontend (`/app/#component=course`)
- **URL base dos cursos:** `https://www.ficaadicapremium.com.br/course/{slug}/`
- **7 Pilares de conteúdo:**
  1. Técnica instrumental
  2. Harmonia
  3. Improvisação
  4. Escalas
  5. Ritmo / Levadas
  6. Repertório / Músicas
  7. Leitura Musical
- **Outros conteúdos:** Composição, Arranjo, Produção, Carreira, História da Música
- **Coordenador pedagógico:** Nelson Faria
- **Professores:** Nelson Faria, Alexandre Carvalho, Débora Gurgel, Michel Caramelo, e outros

## Perfil do Usuário (para geração do plano)

- Guitarrista com experiência intermediária/avançada
- Toca Jazz e MPB em banda
- Guitarra principal: Fender Strat + Hollowbody (jazz)
- Interesse principal: Jazz, improvisação, harmonia avançada, MPB
- Objetivo: aprimoramento, não iniciação
