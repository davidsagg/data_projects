# 🍎 Guia de Instalação para macOS

## Passo a Passo Completo

### 1️⃣ Abra o Terminal
- Pressione `Cmd + Espaço`
- Digite "Terminal"
- Pressione Enter

### 2️⃣ Instale o Node.js

**Opção A: Com Homebrew (Recomendado)**

```bash
# Instale o Homebrew (se não tiver)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instale o Node.js
brew install node@20
```

**Opção B: Download Direto**
1. Acesse: https://nodejs.org/
2. Baixe a versão LTS para macOS
3. Execute o instalador `.pkg`
4. Siga as instruções

**Verifique a instalação:**
```bash
node -v    # Deve mostrar v18.x ou superior
npm -v     # Deve mostrar 9.x ou superior
```

### 3️⃣ Clone o Repositório

```bash
# Vá para a pasta onde quer baixar (exemplo: Desktop)
cd ~/Desktop

# Clone o repositório
git clone https://github.com/davidsagg/work_in_progress.git

# Entre na pasta do projeto
cd work_in_progress/okr-portfolio-dashboard
```

**Não tem Git instalado?**
```bash
# Instale o Git
brew install git

# Ou baixe de: https://git-scm.com/download/mac
```

### 4️⃣ Execute o Setup Automático

```bash
# Dê permissão de execução
chmod +x setup.sh

# Execute o script
./setup.sh
```

O script vai:
- ✅ Verificar se Node.js está instalado
- ✅ Instalar todas as dependências
- ✅ Mostrar os próximos passos

### 5️⃣ Inicie o Servidor

```bash
npm run dev
```

**O navegador vai abrir automaticamente em:**
```
http://localhost:3000
```

> 💡 **Nota:** A porta padrão foi configurada para **3000** (não 5173)

---

## 🎯 Comandos Rápidos

```bash
# Iniciar desenvolvimento
npm run dev

# Parar o servidor
Ctrl + C

# Build de produção
npm run build

# Visualizar build
npm run preview
```

---

## 🔧 Mudar a Porta (Opcional)

Se a porta 3000 também estiver em uso, você pode mudar:

**Opção 1: Edite o arquivo `vite.config.ts`**
```typescript
server: {
  port: 8080, // Mude para a porta que quiser
}
```

**Opção 2: Via linha de comando**
```bash
npm run dev -- --port 8080
```

---

## ⚡ Atalhos do Terminal no Mac

| Atalho | Função |
|--------|--------|
| `Cmd + K` | Limpar terminal |
| `Ctrl + C` | Parar processo |
| `Cmd + T` | Nova aba |
| `Cmd + W` | Fechar aba |
| `↑` | Comando anterior |

---

## 🛠️ Problemas Comuns no macOS

### "Permission denied" ao executar setup.sh

```bash
chmod +x setup.sh
./setup.sh
```

### "command not found: node" (instalou com Homebrew)

```bash
# Adicione ao PATH
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verifique novamente
node -v
```

### "command not found: git"

```bash
# Instale Command Line Tools
xcode-select --install

# Ou instale via Homebrew
brew install git
```

### Porta já em uso

```bash
# Descubra qual processo está usando a porta
lsof -i :3000

# Mate o processo (use o PID da saída acima)
kill -9 [PID]

# Ou use outra porta
npm run dev -- --port 8080
```

### Erro "Cannot find module"

```bash
# Limpe e reinstale
rm -rf node_modules package-lock.json
npm install
```

---

## 📱 Ver de Outros Dispositivos na Mesma Rede

```bash
# Inicie com --host
npm run dev -- --host

# O terminal vai mostrar:
# Local:   http://localhost:3000
# Network: http://192.168.x.x:3000  ← Use este IP
```

Agora você pode acessar do seu iPad, iPhone, etc!

---

## 🎨 Dicas para Desenvolvedores Mac

### VS Code (Editor Recomendado)

```bash
# Instale VS Code via Homebrew
brew install --cask visual-studio-code

# Abra o projeto no VS Code
code .
```

**Extensões úteis:**
- ES7+ React/Redux/React-Native snippets
- Tailwind CSS IntelliSense
- TypeScript Error Translator

### iTerm2 (Terminal Melhorado)

```bash
# Instale iTerm2
brew install --cask iterm2
```

### Oh My Zsh (Shell Melhorado)

```bash
# Instale Oh My Zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

---

## 🚀 Próximos Passos

1. ✅ Projeto rodando em http://localhost:3000
2. 📱 Sistema carregou dados de demonstração
3. 🎯 Explore o menu lateral:
   - **Dashboard** - Visão geral
   - **Portfolio** - Projetos e iniciativas
   - **OKRs** - Objetivos
   - **Timeline** - Milestones

4. 📖 Leia o `QUICKSTART.md` para aprender a usar

---

## 💾 Backup e Dados

Os dados ficam salvos no navegador. Para backup:

```bash
# Abra o Console (Cmd + Option + J no Chrome)
# Execute:
const data = localStorage.getItem('okr-portfolio-data');
console.log(data);
# Copie e salve em um arquivo
```

---

## ✅ Checklist

- [ ] Node.js 18+ instalado (`node -v`)
- [ ] Git instalado (`git --version`)
- [ ] Repositório clonado
- [ ] Dependências instaladas (`npm install`)
- [ ] Servidor iniciado (`npm run dev`)
- [ ] Navegador abriu em http://localhost:3000
- [ ] Dashboard carregou com dados de demonstração

**Tudo funcionando? Parabéns! 🎉**

---

## 📞 Precisa de Ajuda?

- Veja o `INSTALL.md` para mais detalhes
- Leia o `README.md` para documentação completa
- Console com erros? Copie e pesquise no Google

**Comandos úteis para debug:**
```bash
# Logs detalhados
npm run dev --verbose

# Limpar cache
rm -rf node_modules package-lock.json .vite
npm install

# Verificar saúde do projeto
npm run build
```
