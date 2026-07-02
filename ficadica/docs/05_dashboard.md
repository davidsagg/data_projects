# Prompt 05 — Dashboard Web Local

## Como usar este prompt

Execute após o Prompt 04 ter gerado `data/study_plan.json`. Cole no Claude Code.

## PROMPT PARA O CLAUDE CODE:

Crie um dashboard web local para visualizar o catálogo e o plano de estudos do Fica a Dica Premium. Deve rodar 100% offline (sem servidor externo), servido via Python `http.server`.

### Estética e UX

- **Tema:** Dark mode, aesthetic de "escola de música premium"
- **Cores:** Fundo escuro (`#0f0f0f`), dourado (`#c9a84c`), branco suave (`#f0ede8`)
- **Tipografia:** Google Fonts — Playfair Display (títulos) + Inter (corpo)
- **Layout:** Sidebar de navegação + área principal com cards
- **Responsivo:** Funciona bem em MacBook (1440px+)

### Arquivo `dashboard/index.html`

SPA simples com 4 seções navegáveis:

**1. 🎯 Meu Plano**

- Linha do tempo visual das 4 fases (barra de progresso horizontal)
- Cards de cada fase com: título, semanas, foco, lista de cursos
- Cada curso com: nome, instrutor, badge de prioridade (⭐), duração estimada
- Botão "Abrir no site" que leva para a URL do curso

**2. 📚 Catálogo Completo**

- Filtros: Categoria | Nível | Instrutor | Instrumento | Estilo
- Grid de cards de cursos
- Cada card: thumbnail (se disponível), título, instrutor, badge de categoria, duração total, indicador de prioridade colorido
- Click abre modal com detalhes completos (módulos, descrição, link)

**3. 📊 Estatísticas**

- Total de cursos mapeados
- Total de horas de conteúdo
- Distribuição por categoria (gráfico de barras simples em SVG ou CSS)
- Top 5 instrutores por número de cursos
- Horas do plano por fase

**4. ⚙️ Configurações**

- Formulário para editar perfil do usuário (`available_hours_per_week`, etc.)
- Botão "Regenerar Plano" (chama `run_planner.py` via fetch para API local)
- Botão "Atualizar Catálogo" (chama `run_scraper.py` via API local)

### Arquivo `dashboard/server.py`

Mini API Python com `http.server` + `json`:

```python
"""
Servidor local do dashboard.
Uso: python dashboard/server.py
Acesse: http://localhost:8765
"""
# Endpoints:
# GET  /api/courses       → retorna data/courses.json
# GET  /api/study_plan    → retorna data/study_plan.json
# GET  /api/profile       → retorna study_plan/user_profile.json
# POST /api/profile       → salva perfil atualizado
# POST /api/regenerate    → executa run_planner.py e retorna novo plano
# POST /api/rescrape      → executa run_scraper.py (longo — retorna job_id)
# GET  /api/status/{id}   → status de job assíncrono
```

### Arquivo `dashboard/app.js`

JavaScript vanilla (sem framework externo):

- Carrega dados via `fetch('/api/courses')` e `fetch('/api/study_plan')`
- Renderiza cards dinamicamente
- Filtros com estado local
- Modal de detalhes do curso
- Salva preferências de filtro em localStorage

### Arquivo `start_dashboard.sh`

```bash
#!/bin/bash
echo "🎸 Iniciando Fica a Dica Dashboard..."
echo "📡 Acesse: http://localhost:8765"
python dashboard/server.py
```

### Execução final:

1. Inicie o servidor: `python dashboard/server.py`
2. Abra no browser: `http://localhost:8765`
3. Confirme que todas as 4 seções carregam corretamente
4. Teste o filtro de cursos por categoria "improvisação"
5. Mostre screenshot ou descreva o que está renderizando

**NOTA DE QUALIDADE:**

- O dashboard deve parecer um produto premium, não um protótipo
- Use transições CSS suaves (0.2s ease)
- Cards devem ter hover state com elevação (box-shadow)
- Indicadores de prioridade devem ser visualmente claros (cor + estrelas)
- Fontes carregadas do Google Fonts via CDN
