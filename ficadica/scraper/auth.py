import json
import asyncio
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from rich.console import Console
from scraper import config

console = Console()

SESSION_PATH = Path(config.OUTPUT_DIR) / "session.json"
# Login via wp-login.php (formulário padrão WordPress)
LOGIN_URL = f"{config.BASE_URL}/wp-login.php"
CHECK_URL = f"{config.APP_URL}/"


class FicaAdicaAuth:
    """
    Gerencia autenticação no Fica a Dica Premium.

    O site usa WordPress padrão. O login é feito via /wp-login.php
    com campos #user_login e #user_pass.
    Após autenticação, os cookies de sessão são salvos para reutilização.
    """

    async def login(self, page: Page) -> bool:
        """Faz login e retorna True se bem-sucedido."""
        config.validate()
        console.print("[cyan]Navegando para página de login...[/cyan]")

        await page.goto(LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(1)

        # Verificar se já está logado
        if await self.is_logged_in(page):
            console.print("[green]Sessão já ativa.[/green]")
            return True

        # Preencher formulário WordPress padrão
        try:
            await page.wait_for_selector("input#user_login", timeout=10000)
            await page.fill("input#user_login", config.EMAIL)
            await page.fill("input#user_pass", config.PASSWORD)

            # Submeter
            await page.click("input#wp-submit")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

        except Exception as e:
            console.print(f"[red]Erro ao preencher formulário: {e}[/red]")
            return False

        if await self.is_logged_in(page):
            console.print("[green]Login realizado com sucesso.[/green]")
            return True

        # Tentar detectar mensagem de erro do WordPress
        error = await page.query_selector("#login_error, .notice-error")
        if error:
            msg = await error.inner_text()
            console.print(f"[red]Erro de login: {msg.strip()}[/red]")
        else:
            console.print("[red]Login falhou — verifique credenciais no .env[/red]")

        return False

    async def is_logged_in(self, page: Page) -> bool:
        """Verifica se a sessão ainda está ativa navegando para /app/."""
        try:
            await page.goto(CHECK_URL, wait_until="networkidle")
            await asyncio.sleep(2)
            url = page.url
            # Redirecionou para login = sessão inválida
            if "wp-login" in url or "login" in url:
                return False
            html = await page.content()
            # Página do app carregada = autenticado
            return len(html) > 1000
        except Exception:
            return False

    async def save_session(self, context: BrowserContext, path: str = None):
        """Salva cookies em arquivo JSON para reutilização."""
        save_path = Path(path) if path else SESSION_PATH
        cookies = await context.cookies()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(cookies, f, indent=2)
        console.print(f"[dim]Sessão salva em {save_path}[/dim]")

    async def load_session(self, context: BrowserContext, path: str = None) -> bool:
        """Carrega sessão salva. Retorna False se arquivo não existe."""
        load_path = Path(path) if path else SESSION_PATH
        if not load_path.exists():
            return False
        try:
            with open(load_path) as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            console.print(f"[dim]Sessão carregada de {load_path}[/dim]")
            return True
        except Exception as e:
            console.print(f"[yellow]Sessão inválida ({e}), será recriada.[/yellow]")
            return False
