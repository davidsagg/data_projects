# 🎸 BandKit — Show & Event Management for Musicians

**Project Charter · v1.0 · 2026**

| Campo | Valor |
|---|---|
| **Projeto** | BandKit — Show & Event Management |
| **Versão** | 1.0 |
| **Data** | Abril 2026 |
| **Owner** | Dave |
| **Contexto** | Portfolio Técnico — Build to Learn (pós-MusicDNA AI + Trend Radar) |
| **Stack base** | Python · FastAPI · React · SQLite · pdfplumber · ChordPro engine |
| **Plataforma** | Local (Mac) — browser via React + FastAPI. Escalável para web/mobile |
| **Usuários** | Admin (organizador) + Músicos da banda (modo show) |
| **Custo** | Zero — 100% local, sem APIs pagas, sem cloud |
| **Status** | Iniciação |

## 1. Visão do Projeto

BandKit é uma plataforma local de gerenciamento de shows e eventos musicais com dois modos de uso complementares: o **Modo Admin** para o organizador estruturar eventos, setlists e equipe, e o **Modo Músico** para uso durante o show — exibindo cifras, letras e permitindo transposição de tom em tempo real.

O diferencial técnico está no **pipeline de processamento de PDFs digitais:** upload de PDF → extração de texto com pdfplumber → parsing para formato ChordPro proprietário → renderização com transposição dinâmica de acordes. **Nenhuma dependência de serviço externo — tudo processado localmente.**

## 2. Problema & Oportunidade

| 🔴 Problema | 🟡 Oportunidade |
|---|---|
| Organizadores de shows gerenciam setlist, escala de músicos e partituras em ferramentas separadas (WhatsApp, papel, Notion) | Plataforma única que centraliza evento, setlist, equipe e material musical |
| Músicos precisam carregar cadernos de cifras ou tablets com múltiplos apps durante o show | Modo Músico otimizado para o palco: tela limpa, scroll manual, fonte grande |
| Transposição de tom durante o show exige conhecimento de teoria musical ou app dedicado | Transposição automática em 1 clique — o músico escolhe o tom e o app refaz todos os acordes |
| PDFs de cifras não são pesquisáveis nem transponíveis | Pipeline OCR/parsing converte PDF digital em formato estruturado e transponível |
| Apps como iReal Pro e Piascore são focados em partitura, não em gestão de show | BandKit une gestão (admin) e execução (músico) numa mesma plataforma local |

## 3. Dois Modos — Uma Plataforma

**🎛️ MODO ADMIN — Organizador do Show**

- **Calendário de eventos** — visualização mensal/semanal de shows, ensaios e compromissos da banda
- **Gestão de setlist** — montagem da ordem de músicas por show, drag & drop para reordenar
- **Escala de músicos** — definir quem executa cada música (substituições, formações alternativas)
- **Upload de cifras (PDF)** — pipeline de extração: PDF digital → ChordPro proprietário → biblioteca
- **Biblioteca de músicas** — catálogo completo com tags de gênero, tom original, BPM e duração
- **Visão de preparação** — checklist de itens por show: equipamentos, horários, contatos do local

**🎸 MODO MÚSICO — Companion de Palco**

- **Setlist do show atual** — lista simplificada das músicas na ordem de execução
- **Visualizador de cifras** — exibição de letras + acordes com fonte grande, otimizada para palco
- **Transposição de tom** — botões + / − para subir ou descer semitons; acordes recalculados instantaneamente
- **Navegação por setas** — avançar/voltar na cifra com setas laterais (mouse, teclado ou pedal MIDI futuro)
- **Indicação do músico** — destaque visual da seção/instrumento do músico logado
- **Modo noturno** — tema escuro para uso em ambientes com pouca luz (palcos, bares)

## 4. Pipeline de Processamento de Cifras — O Coração Técnico

O diferencial técnico do BandKit é o pipeline que transforma PDFs digitais em cifras transponíveis. Funciona em 4 estágios:

```
PDF → ChordPro → Transposição → Renderização

PDF digital (texto selecionável)
         │
         ▼  pdfplumber
Extração de texto bruto (preserva layout de linhas)
         │
         ▼  ChordPro Parser (regex + heurística)
Detecção de padrões:
  • Linhas de acordes: [A] [Em] [C#m] [G7]       ← tagged como chord line
  • Linhas de letra:   'Preciso me encontrar'     ← tagged como lyric line
  • Seções:            [Intro] [Verso] [Refrão]   ← tagged como section
         │
         ▼  Formato BandKit ChordPro (.bkcp)
{title: Nome da Música}
{artist: Artista}
{key: Am}
{tempo: 120}
[Intro]
[Am]Preciso me [F]encontrar [C]  [G]
Preciso me encontrar
         │
         ▼  ChordTransposer Engine
Tom Am → Cm: [Cm]Preciso me [Ab]encontrar [Eb] [Bb]
         │
         ▼  React Renderer
Cifra renderizada com acordes sobre as sílabas corretas
```

### 4.1 Lógica de Transposição

A transposição segue a teoria musical padrão com mapeamento cromático completo:

```python
# src/chord_engine/transposer.py — lógica central

# Escala cromática — 12 semitons
CHROMATIC = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
ENHARMONIC = {'Db':'C#','Eb':'D#','Gb':'F#','Ab':'G#','Bb':'A#'}

def transpose_chord(chord: str, semitones: int) -> str:
    # Extrai raiz + sufixo (ex: 'C#m7' → raiz='C#', sufixo='m7')
    # Normaliza enarmonias (Db → C#)
    # Desloca N posições no CHROMATIC
    # Reconstrói: nova_raiz + sufixo
    # Ex: transpose('Am', +3) → 'C#m'
    #     transpose('G7', -2) → 'F7'
    ...

def transpose_song(bkcp_content: str, semitones: int) -> str:
    # Para cada linha tagged como chord_line:
    #   Detecta todos os acordes entre colchetes [X]
    #   Aplica transpose_chord() em cada um
    # Retorna o .bkcp completo transposto
    # Letras e seções não são modificadas
    ...
```

## 5. Arquitetura — Local First

```
┌──────────────────────────────────────────────────────────────┐
│                    BANDKIT — ARQUITETURA                       │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│   Browser (React + Vite)                                       │
│   ┌─────────────────────────────────────────────────────┐     │
│   │  Admin Mode          │  Musician Mode                │     │
│   │  ─────────────────   │  ───────────────────          │     │
│   │  Calendar View       │  Setlist View                 │     │
│   │  Event Manager       │  Chord Viewer                 │     │
│   │  Setlist Builder     │  Transposer Controls          │     │
│   │  Song Library        │  Dark Mode                    │     │
│   │  PDF Upload          │                               │     │
│   └───────────────────────────────────────────────────┬─┘     │
│                                                        │       │
│                    REST API (JSON)                     │       │
│                                                        │       │
│   FastAPI (Python 3.11)                                │       │
│   ┌───────────────────────────────────────────────────▼─┐     │
│   │  /events    /setlists    /songs    /musicians        │     │
│   │  /upload    /transpose   /health                     │     │
│   └─────────────────────────────┬───────────────────────┘     │
│                                 │                              │
│         ┌───────────────────────┼──────────────────┐          │
│         │                       │                  │          │
│    ┌────▼────┐          ┌───────▼──────┐   ┌───────▼─────┐    │
│    │ SQLite  │          │  pdfplumber  │   │   Chord     │    │
│    │  (data) │          │  PDF Parser  │   │  Transposer │    │
│    └─────────┘          └──────────────┘   └─────────────┘    │
│                                                                │
│    /bandkit-data/  (pasta local no Mac — persiste os dados)    │
└──────────────────────────────────────────────────────────────┘
```

## 6. Stack Tecnológica

| Camada | Tecnologia | Finalidade | Novo vs projetos anteriores |
|---|---|---|---|
| **Frontend** | React 18 + Vite + TypeScript | SPA com dois modos (Admin/Músico) | 🆕 React — novo no portfólio |
| **UI Components** | Tailwind CSS + shadcn/ui | Design system consistente e rápido | 🆕 shadcn/ui — novo |
| **State Mgmt** | Zustand | Estado global: modo atual, tom, setlist | 🆕 Zustand — novo |
| **Calendar** | react-big-calendar | Visualização de eventos e shows | 🆕 Novo componente |
| **Backend** | FastAPI + Python 3.11 | API REST + servidor de arquivos estáticos | ✅ Reutilizado |
| **Database** | SQLite + SQLAlchemy | Persistência local simples sem servidor | ⚙️ SQLite (vs DuckDB) |
| **Migrations** | Alembic | Versionamento de schema do banco | 🆕 Alembic — novo |
| **PDF Parser** | pdfplumber | Extração de texto de PDFs digitais | 🆕 pdfplumber — novo |
| **Chord Engine** | Python puro (custom) | Parser ChordPro + transposição musical | 🆕 Algoritmo próprio |
| **Testes** | pytest + Vitest (React) | TDD backend + testes de componente frontend | ⚙️ Vitest — novo |
| **Dev Tools** | Vite HMR + uvicorn --reload | Hot reload em frontend e backend | ✅ Padrão XP |
| **Infra** | Mac local — sem Docker na v1 | Simplicidade máxima para prototipagem | ✅ Local first |

## 7. Modelo de Dados — Entidades Principais

```
Musician          Event (Show)          Song (Música)
─────────         ────────────          ─────────────
id                id                    id
name              title                 title
instrument        date                  artist
email             venue                 key_original   ← tom original
role              notes                 key_current    ← tom atual (transposição)
photo_url         status                tempo_bpm
                  checklist_json        duration_sec
                  │                     genre_tags
                  │                     bkcp_content   ← ChordPro proprietário
                  │                     pdf_path       ← arquivo original
                  ▼                     created_at
              Setlist
              ───────
              id
              event_id  ────────────▶ Event
              song_id   ────────────▶ Song
              order_position
              notes            ← observações para esse show
              │
              ▼
          SetlistMusician      ← quem executa cada música
          ───────────────
          setlist_id  ───────▶ Setlist
          musician_id ───────▶ Musician
          instrument_override  ← ex: guitarrista tocando baixo
```

## 8. Metodologia — 7 Fases

| # | Fase | Entregável principal | Novidade técnica |
|---|---|---|---|
| 1 | Planejamento & Arquitetura | ADRs, schema DB, wireframes dos dois modos, estrutura de pastas | SQLite + Alembic, React + Vite setup |
| 2 | User Stories | 18–22 histórias BDD cobrindo Admin e Músico | UX dual-mode: admin vs palco |
| 3 | Casos de Teste | Testes pytest (backend) + Vitest (React components) | Testes de frontend com Vitest — novo |
| 4 | Desenvolvimento XP | Backend FastAPI + React SPA + Chord Engine | Chord transposer engine do zero |
| 5 | TDD | RED → GREEN: 40+ testes backend + 20+ testes React | Testing Library para componentes React |
| 6 | Otimização | Performance do parser, UX do modo músico, PWA offline | PWA + cache offline para palco sem rede |
| 7 | Deploy | App empacotado: `make start` → abre no browser automaticamente | Electron ou script local de setup |

## 9. Restrições & Premissas

| ✅ Premissas | ⚠️ Restrições |
|---|---|
| PDFs são digitais com texto selecionável (não escaneados) | PDFs escaneados ficam fora do escopo da v1 — exigiriam OCR com Tesseract (v2) |
| Mac M2 24GB disponível para dev e uso local | Autenticação simplificada na v1: seleção de perfil sem senha (local, confiável) |
| React + FastAPI como stack definitiva para o mock | Sincronização em tempo real entre devices (admin avança, músico vê) fica para v2 |
| Dados persistem em SQLite local na pasta /bandkit-data | Scroll automático por tempo (teleprompter) fora do escopo v1 — manual |
| Zero custo — sem APIs pagas, sem serviços cloud | Integração com Cifra Club ou Ultimate Guitar fora do escopo (licença) |
| Portfolio + uso próprio — banda pequena (< 10 músicos) | Exportação para outros formatos (PDF, iReal Pro) fica para v2 |

## 10. Estrutura de Pastas

```
bandkit/
  ├── backend/                    ← FastAPI
  │   ├── src/
  │   │   ├── api/               ← routers: events, songs, setlists, musicians
  │   │   ├── models/            ← SQLAlchemy models + Pydantic schemas
  │   │   ├── chord_engine/      ← PDF parser + ChordPro engine + transposer
  │   │   ├── db/                ← SQLite connection + Alembic migrations
  │   │   └── config.py          ← settings (paths, app config)
  │   ├── tests/                 ← pytest: unit + integration
  │   ├── main.py                ← FastAPI app entry point
  │   └── requirements.txt
  │
  ├── frontend/                  ← React + Vite + TypeScript
  │   ├── src/
  │   │   ├── pages/             ← AdminPage, MusicianPage, CalendarPage
  │   │   ├── components/        ← SetlistBuilder, ChordViewer, Transposer
  │   │   ├── store/             ← Zustand: appMode, currentSong, semitones
  │   │   ├── api/               ← axios hooks para FastAPI
  │   │   └── types/             ← TypeScript types espelhando os schemas
  │   ├── tests/                 ← Vitest + Testing Library
  │   ├── index.html
  │   └── vite.config.ts
  │
  ├── bandkit-data/              ← dados locais (gitignored)
  │   ├── bandkit.db             ← SQLite database
  │   └── songs/                 ← PDFs originais + arquivos .bkcp
  │
  ├── docs/                      ← documentação das fases
  ├── Makefile                   ← make dev, make test, make setup
  └── README.md
```

## 11. Próximos Passos — Fase 1

- Criar estrutura de pastas e inicializar repositório Git
- Escrever ADRs: SQLite vs PostgreSQL, React vs Vue, pdfplumber vs PyMuPDF, formato ChordPro vs JSON puro
- Definir schema completo do SQLite com Alembic (models + primeira migration)
- Prototipar o ChordPro parser em notebook: carregar 1 PDF real e validar extração
- Definir wireframes dos dois modos (Admin e Músico) como markdown ou Figma básico
- Setup do monorepo: backend (FastAPI + uvicorn) + frontend (React + Vite) rodando em paralelo
- Makefile com: `make dev` (sobe backend + frontend), `make test`, `make setup`

---

*BandKit · Project Charter v1.0 · Build to Learn*
