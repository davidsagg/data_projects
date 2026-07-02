# Prompt 06 — Troubleshooting: SPA e Seletores Dinâmicos

## Quando usar

Se o Prompt 02 falhar porque o conteúdo não carrega (site usa React/SPA), cole este prompt no Claude Code para fazer diagnóstico e ajuste.

## PROMPT PARA O CLAUDE CODE:

O scraper do Fica a Dica Premium está com problemas para extrair conteúdo porque o site usa React (SPA). Preciso de diagnóstico e estratégia alternativa.

### Passo 1 — Diagnóstico via DevTools Automation

Crie o script `debug/inspect_site.py` que:

1. Abre o Playwright com `headless=False` (janela visível)
2. Faz login normalmente
3. Navega para `/cursos/`
4. Aguarda 3 segundos após networkidle
5. Captura e salva:
   - Screenshot em `debug/screenshot_cursos.png`
   - HTML completo em `debug/page_source_cursos.html`
   - Lista de todas as requisições de rede (XHR/fetch) em `debug/network_log.json`
   - Lista de todos os seletores CSS presentes na página em `debug/selectors.txt`

Execute e analise o `network_log.json` para identificar a API REST que o React usa para carregar os cursos. Sites WooCommerce + LearnDash normalmente chamam:

- `/wp-json/ldlms/v2/courses`
- `/wp-json/wp/v2/sfwd-courses`
- `/wp-json/learndash/v2/courses`
- Ou uma API customizada do plugin usado

### Passo 2 — Estratégia via API REST (se encontrada)

Se encontrar chamadas à API REST no network_log, crie `scraper/api_client.py` com:

```python
class FicaAdicaAPIClient:
    """
    Acessa a API REST do WordPress/LearnDash diretamente,
    usando os cookies de sessão do Playwright para autenticação.

    Muito mais eficiente que scraping de HTML.
    """

    def __init__(self, session_cookies: dict):
        self.session = requests.Session()
        self.session.cookies.update(session_cookies)

    async def get_all_courses(self) -> list[dict]:
        """GET /wp-json/ldlms/v2/courses?per_page=100"""

    async def get_course_lessons(self, course_id: int) -> list[dict]:
        """GET /wp-json/ldlms/v2/courses/{id}/lessons"""

    async def get_lesson_detail(self, lesson_id: int) -> dict:
        """GET /wp-json/ldlms/v2/lessons/{id}"""

    async def get_user_progress(self) -> dict:
        """GET /wp-json/ldlms/v2/users/me/course-progress"""
```

### Passo 3 — Estratégia híbrida (fallback)

Se não encontrar API REST, adapte o crawler para usar **intercepção de rede** do Playwright:

```python
# Intercepta todas as chamadas XHR/fetch durante a navegação
async def setup_network_interceptor(page: Page, captured: list):
    async def handle_response(response):
        if 'course' in response.url or 'lesson' in response.url:
            try:
                data = await response.json()
                captured.append({'url': response.url, 'data': data})
            except:
                pass

    page.on('response', handle_response)
```

### Passo 4 — Estratégia de extração por scroll

Se o conteúdo carrega via infinite scroll ou lazy load:

```python
async def scroll_and_collect(page: Page) -> list[dict]:
    """
    Scrola a página gradualmente e coleta elementos conforme aparecem.
    """
    items = []
    last_count = 0

    while True:
        # Scroll para baixo
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)

        # Coleta elementos visíveis
        current_items = await page.query_selector_all('.course-card, .ld-course-list-item')

        if len(current_items) == last_count:
            break  # Chegou ao fim

        last_count = len(current_items)
        # Extrai dados de cada item...

    return items
```

Execute `python debug/inspect_site.py` e mostre:

1. O conteúdo de `debug/network_log.json` (filtrado para chamadas relevantes)
2. Os primeiros 50 seletores CSS encontrados
3. Recomendação de qual estratégia usar (API REST / Intercepção / Scroll)
