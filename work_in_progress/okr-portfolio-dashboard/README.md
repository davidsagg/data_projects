# OKR Portfolio Dashboard

Sistema moderno de gestão de OKRs (Objectives and Key Results) e portfolio de projetos pessoais e profissionais.

## 📋 Sobre o Projeto

Este é um sistema completo para gerenciamento estratégico de objetivos, projetos e iniciativas, com foco em:

- **Visão Estratégica**: Dashboard com visão geral de iniciativas, progresso e red flags
- **Gestão de OKRs**: Acompanhamento de objetivos e resultados-chave por categoria
- **Timeline Visual**: Visualização de milestones e eventos importantes
- **Portfolio de Projetos**: Gerenciamento de projetos e ideias organizados por categoria
- **Múltiplas Categorias**: Trabalho, Treino, Música, Pessoal, Aprendizado, etc.
- **Persistência Local**: Dados salvos automaticamente no navegador (localStorage)

## ✨ Funcionalidades

### Dashboard Principal
- Estatísticas gerais (projetos ativos, OKRs, red flags, milestones)
- Visão dos principais projetos ativos com progresso
- OKRs em andamento com status
- Lista de red flags com priorização por severidade

### Gestão de OKRs
- Criação de objetivos com múltiplos resultados-chave
- Acompanhamento de progresso individual e geral
- Filtros por categoria
- Status: Não Iniciado, Em Progresso, Em Risco, Concluído

### Timeline
- Visualização de milestones organizados por mês
- Filtros por categoria e status (próximos/todos)
- Marcação de milestones como concluídos
- Indicadores visuais para milestones atrasados

### Portfolio
- **Projetos**: Gerenciamento completo com status, progresso, milestones e red flags
- **Iniciativas**: Gestão de ideias e iniciativas futuras
- Filtros por categoria e status
- Priorização (Baixa, Média, Alta, Crítica)

## 🚀 Tecnologias Utilizadas

- **React 18** - Biblioteca UI
- **TypeScript** - Type safety
- **Vite** - Build tool e dev server
- **Tailwind CSS v4** - Estilização moderna
- **Lucide React** - Ícones
- **date-fns** - Manipulação de datas
- **Context API** - State management
- **LocalStorage** - Persistência de dados

## 🛠️ Instalação e Uso

### Pré-requisitos
- Node.js 18+ instalado
- npm ou yarn

### Instalação

```bash
# Clone o repositório (se aplicável)
git clone <seu-repositório>
cd okr-portfolio-dashboard

# Instale as dependências
npm install

# Execute o servidor de desenvolvimento
npm run dev
```

O sistema estará disponível em `http://localhost:5173`

### Build para Produção

```bash
# Cria build otimizado
npm run build

# Visualiza o build localmente
npm run preview
```

## 📁 Estrutura do Projeto

```
src/
├── components/
│   ├── Dashboard/        # Componentes do dashboard
│   ├── OKRs/            # Gestão de OKRs
│   ├── Timeline/        # Timeline de milestones
│   ├── Portfolio/       # Portfolio de projetos
│   ├── Layout/          # Layout e navegação
│   └── common/          # Componentes reutilizáveis
├── contexts/            # Context API
├── types/               # Tipos TypeScript
├── utils/               # Utilitários e dados demo
├── hooks/               # Custom hooks
├── App.tsx             # Componente principal
└── main.tsx            # Entry point
```

## 🎯 Como Usar

### Primeiro Acesso
O sistema carrega automaticamente dados de demonstração no primeiro acesso para você explorar as funcionalidades.

### Navegação
Use o menu lateral para navegar entre:
- **Dashboard**: Visão geral
- **Portfolio**: Gerenciar projetos e iniciativas
- **OKRs**: Gerenciar objetivos
- **Timeline**: Visualizar milestones

### Categorias Disponíveis
- 🏢 Trabalho
- 💪 Treino
- 🎵 Música
- 👤 Pessoal
- 📚 Aprendizado
- ➕ Outro

### Dicas de Uso
1. **Comece pelos OKRs**: Defina seus objetivos trimestrais
2. **Crie Projetos**: Vincule projetos aos seus OKRs
3. **Adicione Milestones**: Marque eventos importantes nos projetos
4. **Monitore Red Flags**: Identifique e resolva bloqueios
5. **Use a Timeline**: Visualize o cronograma geral

### Gerenciamento de Dados
- **Dados Salvos Automaticamente**: Todas as alterações são salvas no navegador
- **Limpar Dados**: Abra o console do navegador e execute:
  ```javascript
  localStorage.clear()
  ```
  Depois recarregue a página para reiniciar com dados demo.

## 🎨 Personalização

### Cores Primárias
As cores podem ser customizadas em `tailwind.config.js`:

```javascript
colors: {
  primary: {
    // Customize aqui
  }
}
```

### Categorias
Adicione novas categorias editando:
- `src/types/index.ts` - Tipo `ProjectCategory`
- `src/components/common/CategoryBadge.tsx` - Configuração visual

## 📝 Roadmap

Funcionalidades planejadas:
- [ ] Formulários de criação/edição de projetos e OKRs
- [ ] Export/Import de dados (JSON)
- [ ] Dark mode
- [ ] Gráficos de progresso
- [ ] Relatórios e insights
- [ ] Sincronização na nuvem (opcional)

## 🤝 Contribuindo

Sinta-se à vontade para:
1. Fazer fork do projeto
2. Criar uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abrir um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 👤 Autor

Desenvolvido com ❤️ para gestão estratégica pessoal e profissional.

---

**Nota**: Este é um projeto de gestão pessoal focado em visão estratégica. Não possui controle detalhado de tarefas, horas ou custos - é ideal para acompanhamento de alto nível de objetivos e projetos.
