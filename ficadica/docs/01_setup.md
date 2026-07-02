# Prompt 01 — Setup do Ambiente

## Como usar este prompt

Cole este texto diretamente no Claude Code (terminal claude) para configurar o projeto.

## PROMPT PARA O CLAUDE CODE:

Preciso configurar um projeto Python para fazer scraping autenticado do site <https://www.ficaadicapremium.com.br> — uma plataforma de cursos de música com autenticação WooCommerce e frontend em SPA (React/JavaScript).

Por favor:

1. **Crie o arquivo `requirements.txt`** com as seguintes dependências:

   ```
   playwright==1.44.0
   beautifulsoup4==4.12.3
   requests==2.32.3
   python-dotenv==1.0.1
   pandas==2.2.2
   rich==13.7.1
   aiohttp==3.9.5
   lxml==5.2.2
   ```

2. **Crie o arquivo `.env.example`** com o template:

   ```
   FAD_EMAIL=seu_email@exemplo.com
   FAD_PASSWORD=sua_senha_aqui
   FAD_BASE_URL=https://www.ficaadicapremium.com.br
   FAD_APP_URL=https://www.ficaadicapremium.com.br/app
   OUTPUT_DIR=./data
   ```

3. **Crie o arquivo `.env`** copiando o `.env.example` (o usuário preencherá as credenciais).

4. **Crie o arquivo `scraper/config.py`** que:
   - Carrega variáveis do `.env` com python-dotenv
   - Expõe as constantes: `EMAIL`, `PASSWORD`, `BASE_URL`, `APP_URL`, `OUTPUT_DIR`
   - Valida que `EMAIL` e `PASSWORD` não estão vazios (raise `ValueError` com mensagem clara)
   - Cria os diretórios `data/raw/`, `data/` se não existirem

5. **Instale as dependências** com `pip install -r requirements.txt`

6. **Instale o Playwright** com `playwright install chromium`

7. **Crie um script `check_env.py`** na raiz que:
   - Verifica se o `.env` está configurado com credenciais reais
   - Testa conectividade com o site
   - Imprime um relatório de status usando rich

Ao final, execute `python check_env.py` e mostre o resultado.

**IMPORTANTE:** Não hardcode credenciais em nenhum arquivo. Todas as credenciais devem vir exclusivamente do arquivo `.env`.
