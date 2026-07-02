# 🎸 Fica a Dica Premium — Scraper & Plano de Estudos

Ferramenta para mapear automaticamente o catálogo de cursos do [Fica a Dica Premium](https://www.ficaadicapremium.com.br) e gerar um plano de estudos personalizado.

## Pré-requisitos

- Python 3.11+
- Claude Code instalado (`npm install -g @anthropic-ai/claude-code`)
- Assinatura ativa no Fica a Dica Premium

## Como usar — Sequência de Prompts

Execute cada prompt na ordem no **Claude Code** (terminal `claude`):

### 1. Abra o Claude Code no diretório do projeto

```bash
cd ficaadicapremium-scraper
claude
```

### 2. Execute os prompts em sequência

| Prompt | Arquivo | O que faz |
|---|---|---|
| 01 | `prompts/01_setup.md` | Configura ambiente Python + Playwright |
| 02 | `prompts/02_scraper.md` | Cria scraper autenticado |
| 03 | `prompts/03_parser.md` | Parseia e estrutura os dados |
| 04 | `prompts/04_study_plan.md` | Gera plano de estudos |
| 05 | `prompts/05_dashboard.md` | Cria dashboard web local |

**Em caso de problemas com o site (SPA):**

- `prompts/06_troubleshooting_spa.md` — diagnóstico e estratégias alternativas

### 3. Configure suas credenciais

```bash
cp .env.example .env
# Edite .env com seu email e senha do Fica a Dica Premium
```

### 4. Execute o pipeline completo

```bash
python run_scraper.py          # Mapeia todos os cursos
python run_parser.py           # Estrutura os dados
python run_planner.py          # Gera o plano de estudos
python dashboard/server.py     # Inicia o dashboard
# Acesse: http://localhost:8765
```

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `data/courses.json` | Catálogo completo estruturado |
| `data/courses.csv` | Catálogo em planilha |
| `data/catalog.md` | Catálogo legível em Markdown |
| `data/study_plan.json` | Plano de estudos (JSON) |
| `data/study_plan.md` | Plano de estudos (Markdown) |

## Personalização do Plano

Edite `study_plan/user_profile.json` para ajustar:

- Horas disponíveis por semana
- Objetivos de estudo
- Estilos de interesse
- Categorias prioritárias

Depois execute `python run_planner.py` para regenerar o plano.

## Notas Legais

- Esta ferramenta é para uso pessoal do assinante
- Não redistribua o conteúdo extraído
- Respeite os termos de uso do Fica a Dica Premium
