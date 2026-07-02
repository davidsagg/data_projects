# Prompt 02 — Scraper Autenticado com Playwright

## Como usar este prompt

Execute após concluir o Prompt 01. Cole no Claude Code.

## PROMPT PARA O CLAUDE CODE:

Crie o scraper autenticado para o site Fica a Dica Premium usando Playwright (Python, async). O site usa WordPress + WooCommerce com SPA React no frontend.

### Arquivo `scraper/auth.py`

Implemente a classe `FicaAdicaAuth` com:

```python
class FicaAdicaAuth:
    """
    Gerencia autenticação no Fica a Dica Premium.

    O site usa WooCommerce. O login é feito via:
    - POST em https://www.ficaadicapremium.com.br/wp-login.php
    - Ou via formulário em https://www.ficaadicapremium.com.br/minha-conta/

    Após autenticação, os cookies de sessão são salvos para reutilização.
    """

    async def login(self, page: Page) -> bool:
        """Faz login e retorna True se bem-sucedido."""

    async def is_logged_in(self, page: Page) -> bool:
        """Verifica se a sessão ainda está ativa."""

    async def save_session(self, context: BrowserContext, path: str):
        """Salva cookies em arquivo JSON para reutilização."""

    async def load_session(self, context: BrowserContext, path: str) -> bool:
        """Carrega sessão salva. Retorna False se expirada."""
```

**Lógica de login:**

1. Tentar carregar sessão salva em `data/session.json`
2. Se não existir ou estiver expirada, navegar para a página de login
3. Preencher email e senha (vindos de `config.py`)
4. Submeter e aguardar redirect para área do aluno
5. Verificar sucesso testando acesso a `/app/`
6. Salvar sessão para próximas execuções

### Arquivo `scraper/crawler.py`

Implemente a classe `FicaAdicaCrawler` com:

```python
class FicaAdicaCrawler:
    """
    Crawla todos os cursos disponíveis ao assinante logado.

    Estratégia:
    1. Navegar para /cursos/ e coletar todos os slugs de cursos
    2. Para cada curso, navegar para /course/{slug}/ e extrair metadados
    3. Entrar em cada aula e extrair título, duração, descrição
    4. Salvar HTML bruto em data/raw/{slug}.html para reprocessamento
    """

    async def get_course_list(self, page: Page) -> list[dict]:
        """
        Coleta todos os cursos disponíveis.
        Retorna lista de: {slug, title, url, thumbnail_url}
        """

    async def scrape_course(self, page: Page, course_slug: str) -> dict:
        """
        Extrai dados completos de um curso.
        Retorna: {
            slug, title, description, instructor, level,
            total_lessons, total_duration_minutes,
            modules: [{title, lessons: [{title, duration, url, completed}]}]
        }
        """

    async def scrape_all(self) -> list[dict]:
        """
        Método principal: autentica e crawla todos os cursos.
        Mostra progresso com rich.progress.
        Salva checkpoint em data/courses_raw.json a cada 5 cursos.
        """

    async def _save_raw_html(self, slug: str, html: str):
        """Salva HTML bruto para reprocessamento posterior."""

    async def _extract_course_metadata(self, page: Page, slug: str) -> dict:
        """Extrai metadados do cabeçalho do curso (instrutor, nível, etc.)"""

    async def _extract_lessons(self, page: Page) -> list[dict]:
        """
        Extrai lista de aulas.
        ATENÇÃO: O site pode usar React/JS para renderizar o conteúdo.
        Aguardar seletores específicos antes de extrair.
        Usar page.wait_for_selector() com timeout generoso (10s).
        """
```

**Seletores prováveis a testar (inspecionar via DevTools do browser):**

- Lista de cursos: `div.course-card`, `article.course`, `.ld-course-list-item`
- Título do curso: `h1.course-title`, `.entry-title`
- Lista de aulas: `.ld-lesson-item`, `.course-lesson`, `li.lesson`
- Instrutor: `.course-instructor`, `.instructor-name`
- Duração: `.ld-course-meta`, `.course-duration`

**IMPORTANTE:** O site é uma SPA. Após navegação, sempre usar:

```python
await page.wait_for_load_state("networkidle")
await asyncio.sleep(1)  # buffer para JS renderizar
```

### Script `run_scraper.py` na raiz:

```python
"""
Ponto de entrada principal do scraper.
Uso: python run_scraper.py [--resume] [--course SLUG]
"""
```

Com flags:

- `--resume`: retoma de onde parou (usa checkpoint)
- `--course SLUG`: scrapa apenas um curso específico (para debug)
- `--headless`: roda sem abrir janela do browser (default: False para debug)

Execute `python run_scraper.py --course nelsonfaria-escalas` ao final para testar com um único curso e mostrar o resultado.
