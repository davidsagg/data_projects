# 🚀 Guia Rápido - OKR Portfolio Dashboard

## ⚡ Instalação Rápida

### 1️⃣ Pré-requisitos

**Você precisa ter instalado:**
- **Node.js 18 ou superior**
  - Download: https://nodejs.org/
  - Recomendado: versão LTS (Long Term Support)
  - Para verificar se já tem: abra o terminal e digite `node -v`

### 2️⃣ Clone o Repositório

```bash
# Clone o repositório
git clone https://github.com/davidsagg/work_in_progress.git

# Entre na pasta do projeto
cd work_in_progress/okr-portfolio-dashboard
```

### 3️⃣ Instalação Automática

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```batch
setup.bat
```

**Manual (qualquer sistema):**
```bash
npm install
```

### 4️⃣ Executar o Projeto

```bash
npm run dev
```

Abra o navegador em: **http://localhost:5173**

---

## 📦 Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `npm run dev` | Inicia servidor de desenvolvimento |
| `npm run build` | Gera build de produção |
| `npm run preview` | Visualiza build de produção localmente |
| `npm run lint` | Verifica erros no código |

---

## 🎯 Primeiros Passos no Sistema

### Ao abrir pela primeira vez:

1. **O sistema carrega dados de demonstração automaticamente**
   - 3 projetos de exemplo
   - 3 OKRs de exemplo
   - 4 iniciativas de exemplo

2. **Explore o menu lateral:**
   - 📊 **Dashboard** - Visão geral de tudo
   - 📁 **Portfolio** - Projetos e Iniciativas
   - 🎯 **OKRs** - Objetivos e Resultados-Chave
   - 📅 **Timeline** - Milestones organizados por mês

3. **Interaja com os dados:**
   - ✅ Marque milestones como concluídos
   - 🚩 Resolva red flags
   - 🗑️ Exclua projetos/OKRs de exemplo
   - 🔍 Use os filtros por categoria

### Limpar dados de demonstração:

1. Abra o Console do navegador (F12)
2. Digite e execute:
   ```javascript
   localStorage.clear()
   ```
3. Recarregue a página (F5)

---

## 🛠️ Resolução de Problemas

### Erro: "node não encontrado"
**Solução:** Instale Node.js de https://nodejs.org/

### Erro: "porta 5173 já em uso"
**Solução:** Feche outros processos Vite ou mude a porta em `vite.config.ts`

### Erro ao instalar dependências
**Solução:**
```bash
# Limpe o cache e reinstale
rm -rf node_modules package-lock.json
npm install
```

### Página em branco
**Solução:**
1. Verifique o console do navegador (F12)
2. Limpe o localStorage: `localStorage.clear()`
3. Recarregue a página

---

## 📱 Acesso Remoto (opcional)

Para acessar de outros dispositivos na mesma rede:

```bash
npm run dev -- --host
```

Depois acesse pelo IP local (ex: `http://192.168.1.100:5173`)

---

## 🌐 Deploy (Produção)

### Build Local:
```bash
npm run build
```
Arquivos gerados em: `dist/`

### Deploy Gratuito:

**Vercel:**
```bash
npm install -g vercel
vercel
```

**Netlify:**
```bash
npm install -g netlify-cli
netlify deploy
```

**GitHub Pages:**
1. Configure `base` em `vite.config.ts`
2. Use GitHub Actions ou `gh-pages`

---

## 💾 Backup de Dados

Os dados ficam salvos no navegador. Para fazer backup:

1. Abra Console (F12)
2. Execute:
```javascript
// Exportar dados
const data = localStorage.getItem('okr-portfolio-data');
console.log(data); // Copie e salve em um arquivo
```

3. Para restaurar:
```javascript
// Importar dados
const data = '...'; // Cole os dados aqui
localStorage.setItem('okr-portfolio-data', data);
location.reload();
```

---

## 📞 Suporte

- **Documentação completa:** Veja `README.md`
- **Issues:** https://github.com/davidsagg/work_in_progress/issues
- **Código:** Todo código está documentado com TypeScript

---

## ✅ Checklist de Instalação

- [ ] Node.js 18+ instalado
- [ ] Repositório clonado
- [ ] Dependências instaladas (`npm install`)
- [ ] Servidor rodando (`npm run dev`)
- [ ] Navegador aberto em http://localhost:5173
- [ ] Sistema carregou dados de demonstração
- [ ] Navegação funcionando entre páginas

**Pronto! Agora você está usando o OKR Portfolio Dashboard! 🎉**
