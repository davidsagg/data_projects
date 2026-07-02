# 💻 Guia de Instalação Completo

## 📋 Índice
- [Windows](#windows)
- [macOS](#macos)
- [Linux](#linux)
- [Alternativas sem Node.js](#sem-nodejs)

---

## Windows

### Opção 1: Instalação Automática

1. **Instale Node.js**
   - Acesse: https://nodejs.org/
   - Baixe a versão LTS (ex: 20.x.x)
   - Execute o instalador
   - Mantenha as opções padrão
   - Reinicie o computador após instalação

2. **Baixe o projeto**
   - Opção A: Com Git
     ```cmd
     git clone https://github.com/davidsagg/work_in_progress.git
     cd work_in_progress\okr-portfolio-dashboard
     ```
   - Opção B: Download ZIP
     - Baixe de: https://github.com/davidsagg/work_in_progress/archive/refs/heads/claude/okr-portfolio-dashboard-01Sj2efrHVXcbzPRPRAMBe4v.zip
     - Extraia e entre na pasta `okr-portfolio-dashboard`

3. **Execute o setup**
   - Clique duas vezes em `setup.bat`
   - Ou pelo prompt de comando:
     ```cmd
     setup.bat
     ```

4. **Inicie o servidor**
   ```cmd
   npm run dev
   ```

5. **Abra o navegador**
   - Acesse: http://localhost:5173

### Opção 2: Instalação Manual

```cmd
# 1. Verifique Node.js
node -v
npm -v

# 2. Clone/Baixe o projeto
git clone https://github.com/davidsagg/work_in_progress.git
cd work_in_progress\okr-portfolio-dashboard

# 3. Instale dependências
npm install

# 4. Execute
npm run dev
```

### Troubleshooting Windows

**Erro: "Não é possível executar scripts"**
```powershell
# Execute como Administrador no PowerShell:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Erro: "ENOENT" ou "Cannot find module"**
```cmd
# Limpe e reinstale
rmdir /s /q node_modules
del package-lock.json
npm install
```

---

## macOS

### Opção 1: Instalação Automática

1. **Instale Node.js**

   **Com Homebrew (recomendado):**
   ```bash
   # Instale Homebrew se não tiver
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   # Instale Node.js
   brew install node@20
   ```

   **Ou baixe direto:**
   - Acesse: https://nodejs.org/
   - Baixe versão LTS para macOS
   - Execute o instalador .pkg

2. **Clone o projeto**
   ```bash
   git clone https://github.com/davidsagg/work_in_progress.git
   cd work_in_progress/okr-portfolio-dashboard
   ```

3. **Execute o setup**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

4. **Inicie o servidor**
   ```bash
   npm run dev
   ```

### Opção 2: Instalação Manual

```bash
# 1. Verifique Node.js
node -v
npm -v

# 2. Clone o projeto
git clone https://github.com/davidsagg/work_in_progress.git
cd work_in_progress/okr-portfolio-dashboard

# 3. Instale dependências
npm install

# 4. Execute
npm run dev
```

### Troubleshooting macOS

**Erro: "permission denied"**
```bash
# Dê permissão de execução
chmod +x setup.sh
```

**Erro: "command not found: node"**
```bash
# Adicione ao PATH (se instalou com Homebrew)
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## Linux

### Ubuntu/Debian

```bash
# 1. Instale Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 2. Verifique instalação
node -v
npm -v

# 3. Clone o projeto
git clone https://github.com/davidsagg/work_in_progress.git
cd work_in_progress/okr-portfolio-dashboard

# 4. Execute o setup
chmod +x setup.sh
./setup.sh

# 5. Inicie o servidor
npm run dev
```

### Fedora/RHEL/CentOS

```bash
# 1. Instale Node.js
sudo dnf install nodejs npm

# Ou use NodeSource:
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install nodejs

# 2-5. Mesmo processo do Ubuntu acima
```

### Arch Linux

```bash
# 1. Instale Node.js
sudo pacman -S nodejs npm

# 2-5. Mesmo processo do Ubuntu acima
```

### Troubleshooting Linux

**Erro: "EACCES" (permissão negada)**
```bash
# Configure npm para usar diretório do usuário
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## Sem Node.js?

### Alternativa 1: Docker

Se você tem Docker instalado:

```bash
# Crie um Dockerfile na pasta do projeto
cat > Dockerfile << 'EOF'
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
EOF

# Execute
docker build -t okr-dashboard .
docker run -p 5173:5173 okr-dashboard
```

### Alternativa 2: Build Pré-compilado

Se alguém já fez o build:

1. Copie apenas a pasta `dist/`
2. Use qualquer servidor HTTP:

   **Python:**
   ```bash
   cd dist
   python -m http.server 8000
   ```

   **PHP:**
   ```bash
   cd dist
   php -S localhost:8000
   ```

3. Acesse http://localhost:8000

---

## 🌐 Deploy Online (sem servidor próprio)

### Vercel (Grátis)

```bash
# 1. Instale Vercel CLI
npm install -g vercel

# 2. Na pasta do projeto
vercel login
vercel

# Siga as instruções
```

### Netlify (Grátis)

```bash
# 1. Instale Netlify CLI
npm install -g netlify-cli

# 2. Build
npm run build

# 3. Deploy
netlify deploy --prod --dir=dist
```

### GitHub Pages (Grátis)

1. Edite `vite.config.ts`:
```typescript
export default defineConfig({
  base: '/work_in_progress/', // Nome do repositório
  // ...
})
```

2. Build e deploy:
```bash
npm run build
npx gh-pages -d dist
```

---

## ✅ Verificação da Instalação

Execute estes comandos para verificar:

```bash
# Versões instaladas
node -v    # Deve mostrar v18.x.x ou superior
npm -v     # Deve mostrar 9.x.x ou superior

# Teste do projeto
npm run dev  # Deve iniciar sem erros

# Teste do build
npm run build  # Deve compilar sem erros
```

---

## 📞 Ajuda Adicional

**Problemas com Node.js:**
- Documentação oficial: https://nodejs.org/docs/
- Tutorial NVM (gerenciador de versões): https://github.com/nvm-sh/nvm

**Problemas com o projeto:**
- Abra issue no GitHub: https://github.com/davidsagg/work_in_progress/issues
- Veja logs completos: `npm run dev --verbose`

**Erro não listado aqui?**
1. Copie a mensagem de erro completa
2. Pesquise no Google: "vite [sua mensagem de erro]"
3. Ou abra uma issue com detalhes

---

## 🎉 Instalação Bem-Sucedida!

Se você conseguiu abrir http://localhost:5173 e ver o dashboard, está tudo funcionando!

**Próximos passos:**
- Leia o `QUICKSTART.md` para primeiros passos
- Veja o `README.md` para documentação completa
- Explore o sistema com os dados de demonstração
