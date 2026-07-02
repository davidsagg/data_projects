import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from scraper import config
from scraper.auth import FicaAdicaAuth

console = Console()

CHECKPOINT_PATH = Path(config.OUTPUT_DIR) / "courses_raw.json"
RAW_DIR = Path(config.OUTPUT_DIR) / "raw"

REST_API_URL = f"{config.BASE_URL}/wp-json/wp/v2/course"
SPA_COURSE_LIST_URL = f"{config.APP_URL}/#component=course&action=course"


class FicaAdicaCrawler:
    """
    Crawla todos os cursos disponíveis ao assinante logado.

    Estratégia de descoberta (ordem de prioridade):
    1. WP REST API  — /wp-json/wp/v2/course?per_page=100  (paginado, JSON nativo)
    2. SPA React    — /app/#component=course&action=course  (aguarda renderização)
    3. /cursos/     — fallback HTML estático com seletores WPLMS
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.auth = FicaAdicaAuth()

    async def get_course_list(self, page: Page) -> list[dict]:
        """Coleta lista completa de cursos usando múltiplas estratégias."""

        # 1. REST API (mais confiável: JSON paginado, sem renderização JS)
        courses = await self._get_via_rest_api(page)
        if courses:
            console.print(f"[green]REST API: {len(courses)} cursos encontrados[/green]")
            return courses

        # 2. SPA React
        console.print("[yellow]REST API falhou — tentando SPA React...[/yellow]")
        courses = await self._get_via_spa(page)
        if courses:
            console.print(f"[green]SPA: {len(courses)} cursos encontrados[/green]")
            return courses

        # 3. /cursos/ (HTML estático)
        console.print("[yellow]SPA falhou — tentando /cursos/ (HTML estático)...[/yellow]")
        courses = await self._get_via_cursos_page(page)
        console.print(f"[green]/cursos/: {len(courses)} cursos encontrados[/green]")
        return courses

    async def _get_via_rest_api(self, page: Page) -> list[dict]:
        """
        Usa a WP REST API paginada para listar todos os cursos.
        Faz fetch() via JavaScript no contexto do browser (usa cookies da sessão).
        GET /wp-json/wp/v2/course?per_page=100&page=N
        """
        courses = []
        page_num = 1

        # Precisa estar em uma página do domínio para usar os cookies
        if config.BASE_URL not in page.url:
            await page.goto(config.BASE_URL, wait_until="networkidle")

        while True:
            url = f"{REST_API_URL}?per_page=100&page={page_num}&_fields=id,slug,title,link"
            console.print(f"[dim]REST API page {page_num}...[/dim]")

            try:
                result = await page.evaluate(f"""
                    async () => {{
                        const r = await fetch('{url}', {{credentials: 'include'}});
                        const total_pages = r.headers.get('X-WP-TotalPages');
                        const data = await r.json();
                        return {{ data, total_pages: parseInt(total_pages) || 1, status: r.status }};
                    }}
                """)

                if result.get("status") != 200:
                    break

                data = result.get("data", [])
                if not isinstance(data, list) or not data:
                    break

                for item in data:
                    slug = item.get("slug", "")
                    title = item.get("title", {})
                    title_text = title.get("rendered", slug) if isinstance(title, dict) else str(title)
                    link = item.get("link", f"{config.BASE_URL}/course/{slug}/")
                    if slug:
                        courses.append({
                            "slug": slug,
                            "title": title_text,
                            "url": link,
                            "thumbnail_url": "",
                        })

                total_pages = result.get("total_pages", 1)
                if page_num >= total_pages:
                    break
                page_num += 1

            except Exception as e:
                console.print(f"[dim]REST API erro página {page_num}: {e}[/dim]")
                break

        return courses

    async def _get_via_spa(self, page: Page) -> list[dict]:
        """
        Navega para o SPA React e extrai links de cursos após renderização.
        URL: /app/#component=course&action=course
        """
        courses = []
        seen = set()

        try:
            await page.goto(SPA_COURSE_LIST_URL, wait_until="networkidle")
            await asyncio.sleep(4)  # aguarda React renderizar

            # Interceptar links /course/ renderizados pelo SPA
            links = await page.query_selector_all("a[href*='/course/']")
            for link in links:
                href = await link.get_attribute("href") or ""
                if "/course/" not in href:
                    continue
                slug = href.rstrip("/").split("/")[-1]
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                text = (await link.inner_text()).strip()

                # Thumbnail: imagem próxima ao link
                thumb = ""
                try:
                    img = await link.query_selector("img")
                    if not img:
                        parent = await link.evaluate_handle("el => el.closest('.course, .course-card, article, li, .item')")
                        img = await parent.query_selector("img") if parent else None
                    if img:
                        thumb = await img.get_attribute("src") or ""
                except Exception:
                    pass

                courses.append({"slug": slug, "title": text, "url": href, "thumbnail_url": thumb})

            # Scroll para carregar mais (lazy loading / infinite scroll)
            if courses:
                prev_count = 0
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    links = await page.query_selector_all("a[href*='/course/']")
                    for link in links:
                        href = await link.get_attribute("href") or ""
                        slug = href.rstrip("/").split("/")[-1]
                        if slug and slug not in seen:
                            seen.add(slug)
                            text = (await link.inner_text()).strip()
                            courses.append({"slug": slug, "title": text, "url": href, "thumbnail_url": ""})
                    if len(courses) == prev_count:
                        break
                    prev_count = len(courses)

        except Exception as e:
            console.print(f"[dim]SPA erro: {e}[/dim]")

        return courses

    async def _get_via_cursos_page(self, page: Page) -> list[dict]:
        """Fallback: scraping da página /cursos/ (HTML estático WPLMS)."""
        courses_url = f"{config.BASE_URL}/cursos/"
        await page.goto(courses_url, wait_until="networkidle")
        await asyncio.sleep(2)

        courses = []
        seen = set()

        # Seletores WPLMS
        for selector in ["li.course", ".wplms-course", "article.course", "div.course-card", ".elementor-post"]:
            items = await page.query_selector_all(selector)
            if not items:
                continue
            for item in items:
                link = await item.query_selector("a")
                if not link:
                    continue
                href = await link.get_attribute("href") or ""
                slug = href.rstrip("/").split("/")[-1]
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                title_el = await item.query_selector("h2, h3, h4, .course-title, .entry-title")
                title = (await title_el.inner_text()).strip() if title_el else ""
                thumb_el = await item.query_selector("img")
                thumb = await thumb_el.get_attribute("src") if thumb_el else ""
                courses.append({"slug": slug, "title": title, "url": href, "thumbnail_url": thumb or ""})
            if courses:
                break

        # Fallback: qualquer link /course/
        if not courses:
            links = await page.query_selector_all("a[href*='/course/']")
            for link in links:
                href = await link.get_attribute("href") or ""
                slug = href.rstrip("/").split("/")[-1]
                if slug and slug not in seen:
                    seen.add(slug)
                    text = (await link.inner_text()).strip()
                    courses.append({"slug": slug, "title": text, "url": href, "thumbnail_url": ""})

        return courses

    async def scrape_course(self, page: Page, course_slug: str) -> dict:
        """Extrai dados completos de um curso."""
        url = f"{config.BASE_URL}/course/{course_slug}/"
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)

        await self._save_raw_html(course_slug, await page.content())

        metadata = await self._extract_course_metadata(page, course_slug)
        modules = await self._extract_lessons(page)

        return {**metadata, "modules": modules}

    async def _extract_course_metadata(self, page: Page, slug: str) -> dict:
        """Extrai metadados do cabeçalho do curso (seletores WPLMS)."""
        # Título: h1 com classe course_element_text ou primeiro h1
        title = ""
        for sel in ["h1.course_element_text", "h1.entry-title", "h1"]:
            el = await page.query_selector(sel)
            if el:
                title = (await el.inner_text()).strip()
                if title:
                    break

        # Instrutor: link com classe course_instructor
        instructor = ""
        el = await page.query_selector("a.course_instructor")
        if el:
            instructor = (await el.inner_text()).strip()

        # Descrição: div.course_description ou entry-content
        description = ""
        for sel in ["div.course_description", ".wplms-course-description", ".entry-content"]:
            el = await page.query_selector(sel)
            if el:
                description = (await el.inner_text()).strip()[:500]
                if description:
                    break

        return {
            "slug": slug,
            "url": page.url,
            "title": title,
            "description": description,
            "instructor": instructor,
            "level": "",
            "total_lessons": 0,
            "total_duration_minutes": 0,
        }

    async def _extract_lessons(self, page: Page) -> list[dict]:
        """
        Extrai módulos e aulas do curso usando seletores WPLMS reais.

        Estrutura no HTML:
          li.course_section
            label  ← título da seção/módulo
            ul
              li.course_lesson
                span.item_title  ← título da aula
                span.time        ← duração (ex: 00:12:34)
        """
        from bs4 import BeautifulSoup

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        modules = []

        sections = soup.find_all("li", class_="course_section")
        for section in sections:
            label = section.find("label")
            module_title = label.get_text(strip=True) if label else "Módulo"

            lessons = []
            for li in section.find_all("li", class_="course_lesson"):
                title_el = li.find("span", class_="item_title")
                lesson_title = title_el.get_text(strip=True) if title_el else ""
                time_el = li.find("span", class_="time")
                duration = time_el.get_text(strip=True) if time_el else ""
                # Remove ícone de relogio do texto (vicon)
                duration = duration.replace("\n", "").strip()
                # Link: lições do WPLMS não têm href no currículo; URL pode ser construída
                link = li.find("a")
                lesson_url = link.get("href", "") if link else ""
                lessons.append({
                    "title": lesson_title,
                    "url": lesson_url,
                    "duration": duration,
                    "completed": False,
                })

            modules.append({"title": module_title, "lessons": lessons})

        # Fallback: aulas sem seção
        if not modules:
            for li in soup.find_all("li", class_="course_lesson"):
                title_el = li.find("span", class_="item_title")
                lesson_title = title_el.get_text(strip=True) if title_el else ""
                time_el = li.find("span", class_="time")
                duration = time_el.get_text(strip=True).strip() if time_el else ""
                modules.append({
                    "title": "Aulas",
                    "lessons": [{"title": lesson_title, "url": "", "duration": duration, "completed": False}],
                })

        return modules

    async def _save_raw_html(self, slug: str, html: str):
        """Salva HTML bruto para reprocessamento posterior."""
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"{slug}.html"
        path.write_text(html, encoding="utf-8")

    def _browser_args(self) -> dict:
        return {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--js-flags=--max-old-space-size=256",
            ],
        }

    async def _new_authenticated_page(self, pw, cookies: list):
        """Cria um novo browser + context + page já com os cookies carregados."""
        browser = await pw.chromium.launch(**self._browser_args())
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        await context.add_cookies(cookies)
        page = await context.new_page()
        return browser, context, page

    async def scrape_all(self, resume: bool = False, single_course: str = None) -> list[dict]:
        """Método principal: autentica e crawla todos os cursos."""
        results = []

        # Carregar checkpoint se --resume
        if resume and CHECKPOINT_PATH.exists():
            with open(CHECKPOINT_PATH) as f:
                results = json.load(f)
            # Só pula cursos que foram coletados com sucesso (sem chave "error")
            done_slugs = {c["slug"] for c in results if not c.get("error")}
            error_count = sum(1 for c in results if c.get("error"))
            # Remove erros do checkpoint — serão retentados
            results = [c for c in results if not c.get("error")]
            console.print(
                f"[yellow]Retomando: {len(results)} OK, {error_count} erros serão reprocessados.[/yellow]"
            )
        else:
            done_slugs = set()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**self._browser_args())
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()

            # Autenticação
            session_loaded = await self.auth.load_session(context)
            if session_loaded:
                logged = await self.auth.is_logged_in(page)
            else:
                logged = False

            if not logged:
                logged = await self.auth.login(page)
                if not logged:
                    console.print("[red]Falha na autenticação. Abortando.[/red]")
                    await browser.close()
                    return results
                await self.auth.save_session(context)

            # Guardar cookies para reiniciar o browser quando necessário
            session_cookies = await context.cookies()

            # Definir cursos a crawlar
            if single_course:
                courses = [{"slug": single_course, "title": single_course, "url": "", "thumbnail_url": ""}]
            else:
                courses = await self.get_course_list(page)

            to_crawl = [c for c in courses if c["slug"] not in done_slugs]
            console.print(f"[cyan]Cursos a crawlar: {len(to_crawl)}[/cyan]")

            # Fechar browser inicial — será recriado no loop com os cookies
            await browser.close()

            RESTART_EVERY = 20  # reinicia o browser a cada N cursos (previne crash por memória)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Crawling cursos...", total=len(to_crawl))

                browser, context, page = await self._new_authenticated_page(pw, session_cookies)

                for i, course in enumerate(to_crawl):
                    # Restart periódico do browser para liberar memória
                    if i > 0 and i % RESTART_EVERY == 0:
                        console.print(f"[dim]Reiniciando browser (curso {i}/{len(to_crawl)})...[/dim]")
                        await browser.close()
                        browser, context, page = await self._new_authenticated_page(pw, session_cookies)

                    progress.update(task, description=f"[cyan]{course['slug']}[/cyan]")

                    # Tenta até 2 vezes (1 retry em caso de crash)
                    for attempt in range(2):
                        try:
                            data = await self.scrape_course(page, course["slug"])
                            data["thumbnail_url"] = course.get("thumbnail_url", "")
                            total = sum(len(m["lessons"]) for m in data["modules"])
                            data["total_lessons"] = total
                            results.append(data)
                            console.print(
                                f"  [green]✓[/green] {data['title'] or course['slug']} "
                                f"— {total} aulas em {len(data['modules'])} módulos"
                            )
                            break
                        except Exception as e:
                            err_str = str(e)
                            if attempt == 0 and ("crashed" in err_str.lower() or "closed" in err_str.lower()):
                                console.print(f"  [yellow]↺[/yellow] {course['slug']}: browser crash — reiniciando")
                                await browser.close()
                                browser, context, page = await self._new_authenticated_page(pw, session_cookies)
                            else:
                                console.print(f"  [red]✗[/red] {course['slug']}: {err_str[:80]}")
                                results.append({"slug": course["slug"], "error": err_str, "modules": []})
                                break

                    progress.advance(task)

                    # Checkpoint a cada 5 cursos
                    if (i + 1) % 5 == 0:
                        self._save_checkpoint(results)

            await browser.close()

        self._save_checkpoint(results)
        return results

    def _save_checkpoint(self, results: list[dict]):
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        console.print(f"[dim]Checkpoint salvo: {len(results)} cursos em {CHECKPOINT_PATH}[/dim]")
