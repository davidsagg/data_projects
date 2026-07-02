# 🚀 Guia Completo - OKR Portfolio Dashboard

Sistema completo de gestão de OKRs e Portfolio com **frontend React** + **backend Node.js/PostgreSQL**.

---

## 📋 Índice
1. [Pré-requisitos](#pré-requisitos)
2. [Configuração do Backend](#configuração-do-backend)
3. [Configuração do Frontend](#configuração-do-frontend)
4. [Primeiro Acesso](#primeiro-acesso)
5. [Como Usar](#como-usar)
6. [Funcionalidades](#funcionalidades)

---

## ✅ Pré-requisitos

Você precisa ter instalado:
- **Node.js 18+** (https://nodejs.org/)
- **PostgreSQL** rodando na **porta 5433**
- **Git** para clonar o repositório

### Verificar PostgreSQL:

```bash
psql -U postgres -h 127.0.0.1 -p 5433 -c "SELECT version();"
```

Se não estiver rodando, inicie o PostgreSQL.

---

## 🔧 Configuração do Backend

### 1. Entre na pasta do backend:

```bash
cd okr-portfolio-dashboard/backend
```

### 2. Instale as dependências:

```bash
npm install
```

### 3. Gere o Prisma Client:

```bash
npx prisma generate
```

### 4. Crie as tabelas no banco:

```bash
npx prisma migrate dev --name init
```

Isso cria **8 tabelas**:
- users
- projects
- objectives
- key_results
- milestones
- red_flags
- initiatives

### 5. Popule com dados de exemplo:

```bash
npm run prisma:seed
```

Cria:
- ✅ Usuário: `user@example.com` / `password123`
- ✅ 3 projetos
- ✅ 3 OKRs
- ✅ 4 iniciativas

### 6. Inicie o backend:

```bash
npm run dev
```

✅ Backend rodando em: **http://localhost:3001**

---

## 💻 Configuração do Frontend

### 1. Volte para a raiz e entre no frontend:

```bash
cd ..  # volta para okr-portfolio-dashboard
npm install
```

### 2. Inicie o frontend:

```bash
npm run dev
```

✅ Frontend rodando em: **http://localhost:3000**

O navegador deve abrir automaticamente!

---

## 🎯 Primeiro Acesso

### 1. Abra o navegador em:
```
http://localhost:3000
```

### 2. Você verá a tela de LOGIN

Use as credenciais de demonstração:
- **Email**: `user@example.com`
- **Senha**: `password123`

### 3. Ou crie uma nova conta:
- Clique em "Não tem conta? Registre-se"
- Preencha email, senha e nome (opcional)
- Clique em "Criar Conta"

---

## 🎨 Como Usar

### 📊 Dashboard
- Veja estatísticas gerais
- Projetos ativos
- OKRs em andamento
- Red flags ativos

### 📁 Portfolio

**Criar Novo Projeto:**
1. Clique em "Novo Projeto"
2. Preencha:
   - Título e Descrição
   - Categoria (Trabalho, Treino, Música, etc)
   - Status e Prioridade
   - Datas
   - Tags (opcional)
3. Clique em "Criar Projeto"

**Criar Nova Iniciativa:**
1. Clique em "Iniciativas"
2. Clique em "Nova Iniciativa"
3. Preencha os dados
4. Defina esforço e impacto estimados
5. Salvar

### 🎯 OKRs

**Criar Novo OKR:**
1. Vá para "OKRs"
2. Clique em "Novo OKR"
3. Defina o Objetivo
4. Adicione Resultados-Chave (Key Results):
   - Descrição
   - Meta e valor atual
   - Unidade (%, km, usuários, etc)
   - Status
5. Pode adicionar múltiplos KRs
6. Clique em "Criar OKR"

### 📅 Timeline

- Visualize todos os milestones
- Filtre por categoria
- Marque milestones como concluídos
- Veja próximos eventos (30 dias)

---

## ⚡ Funcionalidades Principais

### ✅ Autenticação
- Login/Logout seguro com JWT
- Registro de novos usuários
- Dados isolados por usuário

### ✅ Projetos
- Criar, editar, deletar
- Categorias múltiplas
- Progresso (0-100%)
- Status: Planning, Active, On-hold, Completed
- Prioridade: Low, Medium, High, Critical
- Milestones com datas
- Red flags com severidade

### ✅ OKRs (Objectives & Key Results)
- Criar objetivos estratégicos
- Múltiplos resultados-chave por objetivo
- Tracking de progresso automático
- Status: Not started, In progress, At risk, Completed
- Organização por trimestre

### ✅ Iniciativas
- Banco de ideias
- Esforço estimado (Pequeno, Médio, Grande)
- Impacto potencial (Baixo, Médio, Alto)
- Status: Idea, Planned, In progress, Completed, Abandoned

### ✅ Timeline
- Visualização temporal de milestones
- Filtros por categoria e status
- Indicadores de atraso
- Agrupamento por mês

### ✅ Dashboard
- Estatísticas em tempo real
- Visão dos projetos ativos
- OKRs em andamento
- Red flags não resolvidos
- Milestones próximos (30 dias)

---

## 🔄 Fluxo de Trabalho Recomendado

1. **Defina OKRs** trimestrais
2. **Crie Projetos** relacionados aos OKRs
3. **Adicione Milestones** aos projetos
4. **Monitore Red Flags**
5. **Use Iniciativas** para ideias futuras
6. **Acompanhe no Dashboard**

---

## 🛠️ Comandos Úteis

### Backend:
```bash
cd backend
npm run dev              # Iniciar servidor
npx prisma studio        # UI visual do banco
npx prisma migrate dev   # Criar migrations
npm run prisma:seed      # Popular dados
```

### Frontend:
```bash
npm run dev              # Iniciar frontend
npm run build            # Build de produção
```

### Ambos:
```bash
# Terminal 1 - Backend
cd backend && npm run dev

# Terminal 2 - Frontend
cd .. && npm run dev
```

---

## 📊 Visualizar Banco de Dados

```bash
cd backend
npx prisma studio
```

Abre em: **http://localhost:5555**

Você pode ver/editar todas as tabelas visualmente!

---

## 🔐 Segurança

✅ **Implementado:**
- Senhas hasheadas com bcrypt
- JWT com expiração (7 dias)
- Validação de inputs
- Dados isolados por usuário
- CORS configurado
- Middleware de autenticação

⚠️ **Para Produção:**
- Mude `JWT_SECRET` no `.env` do backend
- Use HTTPS
- Configure rate limiting
- Adicione logs adequados

---

## 🐛 Troubleshooting

### Backend não inicia:
```bash
# Verifique PostgreSQL
psql -U postgres -h 127.0.0.1 -p 5433

# Regenere Prisma
cd backend
rm -rf node_modules
npm install
npx prisma generate
```

### Frontend não conecta:
1. Verifique se backend está rodando (porta 3001)
2. Verifique arquivo `.env` no frontend:
   ```
   VITE_API_URL=http://localhost:3001/api
   ```
3. Limpe cache:
   ```bash
   rm -rf node_modules .vite
   npm install
   ```

### Erro "Token expired":
- Faça logout e login novamente
- Token expira em 7 dias

### Limpar todos os dados:
```bash
cd backend
npx prisma migrate reset
npm run prisma:seed
```

---

## 📁 Estrutura do Projeto

```
okr-portfolio-dashboard/
├── backend/                # API Node.js/Express
│   ├── prisma/
│   │   ├── schema.prisma   # Schema do banco
│   │   └── seed.js         # Dados de exemplo
│   ├── src/
│   │   ├── routes/         # Rotas da API
│   │   ├── middleware/     # Auth middleware
│   │   └── server.js       # Servidor principal
│   ├── .env                # Config do backend
│   └── package.json
│
├── src/                    # Frontend React
│   ├── components/
│   │   ├── Auth/           # Login/Register
│   │   ├── Dashboard/      # Dashboard
│   │   ├── Forms/          # Formulários
│   │   ├── OKRs/           # Gestão de OKRs
│   │   ├── Portfolio/      # Projetos e Iniciativas
│   │   ├── Timeline/       # Timeline
│   │   ├── Layout/         # Layout e navegação
│   │   └── common/         # Componentes comuns
│   ├── contexts/
│   │   ├── AppContext.tsx  # State (deprecado)
│   │   └── AuthContext.tsx # Autenticação
│   ├── services/
│   │   └── api.ts          # API client
│   ├── types/              # TypeScript types
│   └── App.tsx             # App principal
│
├── .env                    # Config do frontend
└── package.json
```

---

## 🎉 Pronto para Usar!

Agora você tem um sistema completo de gestão de OKRs e Portfolio:

✅ Backend com PostgreSQL rodando
✅ Frontend conectado ao backend
✅ Autenticação funcionando
✅ Formulários para criar dados
✅ Dashboard com estatísticas
✅ Dados persistidos no banco

**Próximos passos:**
1. Login com `user@example.com` / `password123`
2. Explore os dados de demonstração
3. Crie seus próprios projetos e OKRs
4. Personalize para suas necessidades!

---

## 📝 Licença

MIT License - Use livremente!

---

**Dúvidas?**
- Veja `README.md` na raiz
- Veja `backend/README.md` para detalhes da API
- Use Prisma Studio para debug do banco
