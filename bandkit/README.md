<!-- markdownlint-disable MD033 MD041 -->
<h1 align="center">🎸 BandKit</h1>
<p align="center"><strong>Show & Event Management for Working Bands</strong></p>
<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688">
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6">
  <img alt="Tests" src="https://img.shields.io/badge/tests-43%20green-success">
  <img alt="Coverage" src="https://img.shields.io/badge/backend%20coverage-85%25-success">
</p>

<p align="center">
  <a href="#english">🇬🇧 English</a> · <a href="#português">🇧🇷 Português</a>
</p>

---

## English

BandKit is a lightweight, **local-first** web app for bands that gig. It puts everything a band needs to run a show in one place: scheduling events, building setlists, storing chord sheets (ChordPro format), and displaying them live on stage — with **real-time transposition** and **offline support** via PWA.

The app runs as a local server on a laptop or tablet. During a show, every musician connects from their own phone or tablet and follows along in the chord viewer, navigating sections and transposing on the fly without ever touching the admin interface.

### Why it exists — the "Build To Learn" story

BandKit is part of my **Build To Learn** portfolio: projects I build end-to-end to deepen specific engineering skills, not just to ship a feature. It was chosen deliberately for the areas it forced me into, all new to my previous projects (MusicDNA AI, Trend Radar):

- A **full React 18 + TypeScript + Vite** frontend (my previous projects were Python/Streamlit).
- A **dual-mode UX** problem — the same data serving a calm "admin" workflow and a high-stakes, glanceable "stage" workflow.
- A **domain algorithm written from scratch**: a ChordPro parser and a music-theory-correct chord transposer.
- **PWA / offline** engineering for a real constraint: stages and bars with no reliable network.
- **TDD across two languages** (pytest + Vitest), ending at **43 green tests**.

It was built in **7 phases** (charter → user stories → test cases → XP development → TDD → optimization → deploy), documented in [`docs/`](docs/).

### The technical heart — the chord pipeline

The differentiator is the pipeline that turns a digital PDF chord sheet into a transposable, stage-ready score:

```
PDF (selectable text)
      │  pdfplumber
      ▼
Raw text (line layout preserved)
      │  ChordPro parser (regex + heuristics)
      ▼   tags each line: chord line · lyric line · [section]
BandKit ChordPro (.bkcp)
      │  ChordTransposer engine
      ▼   Am → Cm: shifts every chord by N semitones, lyrics untouched
React renderer
      ▼
Chords aligned above the right syllables, large-type, dark stage view
```

Transposition follows standard 12-tone chromatic theory with enharmonic normalization (`Db → C#`), splitting each chord into **root + suffix** (`C#m7` → root `C#`, suffix `m7`), shifting the root, and rebuilding. The same logic is mirrored in JavaScript on the frontend so the stage view can transpose instantly with zero round-trips.

### Two modes, one platform

**🎛️ Admin Mode**
- **Calendar** — create shows, rehearsals and recordings on a monthly/weekly view
- **Song Library** — upload PDF chord sheets; the parser extracts chords and merges them inline with lyrics automatically
- **Setlist Builder** — drag-and-drop songs into a per-event setlist, reorder in real time
- **Musician assignment** — define who plays each song (substitutions, alternate line-ups)

**🎸 Musician Mode (stage view)**
- Sidebar lists the next show's setlist
- Tap a song → full chord sheet in large text on a dark background
- `+` / `−` (or keyboard) transpose all chords instantly
- `←` / `→` (or keyboard) jump between song sections
- Screen stays awake via the **WakeLock API** — no phones going dark mid-song
- Works **offline** after first load (PWA + Service Worker)

### Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy · Alembic · SQLite |
| PDF parsing | pdfplumber · custom ChordPro parser |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS |
| State | Zustand (persisted to localStorage) |
| Routing | React Router v6 |
| Offline | vite-plugin-pwa · Workbox (StaleWhileRevalidate) |
| Tests | pytest + pytest-cov (backend) · Vitest + Testing Library (frontend) |
| Dev env | VS Code DevContainer · Docker Compose (optional) |

### Quick Start

```bash
# 1. Clone (open in DevContainer for the batteries-included setup)
git clone <repo-url> && cd bandkit

# 2. Install everything
make setup        # creates venv, installs deps, runs migrations, npm install

# 3. Run backend + frontend with hot reload
make dev
# → API:  http://localhost:8000/docs
# → App:  http://localhost:5174
```

> **Requires:** Python 3.11+, Node 20+. Docker + VS Code DevContainer optional but recommended.

### Uploading a chord sheet

1. Go to **Músicas → Upload PDF**
2. Select any PDF chord sheet in ChordPro-compatible format
3. BandKit auto-extracts title, artist, key and chords (`parse_status: parsed`)
4. Open any event → add the song to the setlist
5. In Musician Mode, tap the song — the chord viewer is ready

If automatic parsing fails (`parse_status: failed`), open the song in the library and edit the `.bkcp` content directly in the textarea.

### Tests

```bash
make test
# Backend : 37 tests · 85% coverage (pytest)
# Frontend:  6 tests (Vitest — ChordViewer, TransposeControls)
# Total   : 43 green
```

### Project structure

```
bandkit/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI routers (musicians, songs, events, setlists)
│   │   ├── chord_engine/ # ChordPro parser + transposer
│   │   ├── db/           # SQLAlchemy session + get_db
│   │   └── models/       # ORM models + Pydantic schemas
│   ├── alembic/          # Database migrations
│   └── tests/            # pytest suite
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios client wrappers
│   │   ├── components/   # ChordViewer, TransposeControls, EventForm, SetlistBuilder
│   │   ├── pages/        # ProfileSelector, AdminLayout, MusicianLayout, ...
│   │   ├── store/        # Zustand stores (session + musician transposition)
│   │   └── utils/        # JS chord transposition (mirrors the Python engine)
│   └── tests/            # Vitest suite
├── docs/                 # phase docs (00_project_charter.md, ...)
└── bandkit-data/         # SQLite db + uploaded PDFs (gitignored)
```

### API

Interactive docs at `http://localhost:8000/docs` while the backend runs.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/musicians` | List musicians |
| `POST` | `/api/musicians` | Create musician |
| `GET` | `/api/events` | List events |
| `POST` | `/api/events` | Create event |
| `GET` | `/api/songs` | List songs |
| `POST` | `/api/songs/upload` | Upload PDF and parse chords |
| `POST` | `/api/songs/{id}/transpose` | Transpose `.bkcp` by N semitones |
| `GET` | `/api/events/{id}/setlist` | Get an event's setlist |
| `POST` | `/api/events/{id}/setlist` | Add song to setlist |
| `PUT` | `/api/events/{id}/setlist/reorder` | Reorder setlist items |

### What I explored & learned

- **Dual-mode UX is a data problem, not a UI problem.** The same setlist entity had to feel effortless in admin and unmissable on stage. Modeling `MusicalExecution` as independent from the setlist (so the stage order can differ from the planning order) was the refactor that unlocked it.
- **Parsing real-world chord sheets is messy.** PDFs mix tablature, chord diagrams and Spanish key markers (`Tono:`); the parser needed heuristics and an always-available manual-edit fallback rather than pretending extraction is perfect.
- **Mirror the algorithm, don't call it.** Re-implementing transposition in JS on the frontend removed every network round-trip from the most latency-sensitive stage action.
- **DevContainers pay off** for a Python+Node monorepo — but expose real gotchas (Vite proxy + port forwarding, CORS, `--host 0.0.0.0`) that the git history documents.

### Roadmap

- Real-time sync between devices (admin advances → musicians follow)
- Time-based auto-scroll (teleprompter mode)
- OCR for scanned (non-digital) PDFs via Tesseract
- Export to PDF / iReal Pro

---

## Português

BandKit é um web app leve e **local-first** para bandas que fazem shows. Reúne num só lugar tudo que uma banda precisa para tocar: agenda de eventos, montagem de setlists, biblioteca de cifras (formato ChordPro) e exibição ao vivo no palco — com **transposição de tom em tempo real** e **funcionamento offline** via PWA.

O app roda como servidor local num laptop ou tablet. Durante o show, cada músico conecta pelo próprio celular ou tablet e acompanha no visualizador de cifras, navegando entre seções e transpondo na hora, sem nunca tocar na interface de admin.

### Por que existe — a história "Build To Learn"

O BandKit faz parte do meu portfólio **Build To Learn**: projetos construídos de ponta a ponta para aprofundar habilidades específicas de engenharia, não apenas para entregar uma feature. Foi escolhido de propósito pelas áreas em que me obrigava a entrar, todas novas em relação aos projetos anteriores (MusicDNA AI, Trend Radar):

- Um frontend **React 18 + TypeScript + Vite** de verdade (antes eu trabalhava em Python/Streamlit).
- Um problema de **UX de modo duplo** — os mesmos dados servindo um fluxo tranquilo de "admin" e um fluxo de palco, crítico e de leitura instantânea.
- Um **algoritmo de domínio do zero**: parser ChordPro + transpositor de acordes fiel à teoria musical.
- Engenharia **PWA / offline** para uma restrição real: palcos e bares sem rede confiável.
- **TDD em duas linguagens** (pytest + Vitest), terminando em **43 testes verdes**.

Construído em **7 fases** (charter → user stories → casos de teste → desenvolvimento XP → TDD → otimização → deploy), documentadas em [`docs/`](docs/).

### O coração técnico — o pipeline de cifras

O diferencial é o pipeline que transforma um PDF digital de cifra em uma partitura transponível e pronta para o palco:

```
PDF (texto selecionável)
      │  pdfplumber
      ▼
Texto bruto (layout de linhas preservado)
      │  Parser ChordPro (regex + heurística)
      ▼   marca cada linha: linha de acorde · linha de letra · [seção]
BandKit ChordPro (.bkcp)
      │  Engine ChordTransposer
      ▼   Am → Cm: desloca cada acorde em N semitons, letra intacta
Renderizador React
      ▼
Acordes alinhados sobre a sílaba certa, fonte grande, tela escura de palco
```

A transposição segue a teoria cromática de 12 semitons com normalização de enarmonia (`Db → C#`): separa cada acorde em **raiz + sufixo** (`C#m7` → raiz `C#`, sufixo `m7`), desloca a raiz e reconstrói. A mesma lógica é espelhada em JavaScript no frontend, para o modo palco transpor instantaneamente, sem ida e volta ao servidor.

### Dois modos, uma plataforma

**🎛️ Modo Admin**
- **Calendário** — cria shows, ensaios e gravações em visão mensal/semanal
- **Biblioteca de músicas** — upload de PDFs; o parser extrai acordes e os mescla à letra automaticamente
- **Montador de setlist** — arrasta e solta músicas na setlist do evento, reordena em tempo real
- **Escala de músicos** — define quem toca cada música (substituições, formações alternativas)

**🎸 Modo Músico (visão de palco)**
- Barra lateral lista a setlist do próximo show
- Toque numa música → cifra completa em fonte grande, fundo escuro
- `+` / `−` (ou teclado) transpõem todos os acordes na hora
- `←` / `→` (ou teclado) pulam entre seções
- Tela fica acesa via **WakeLock API** — nada de celular apagando no meio da música
- Funciona **offline** após o primeiro carregamento (PWA + Service Worker)

### Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy · Alembic · SQLite |
| Parsing de PDF | pdfplumber · parser ChordPro próprio |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS |
| Estado | Zustand (persistido no localStorage) |
| Rotas | React Router v6 |
| Offline | vite-plugin-pwa · Workbox (StaleWhileRevalidate) |
| Testes | pytest + pytest-cov (backend) · Vitest + Testing Library (frontend) |
| Ambiente de dev | VS Code DevContainer · Docker Compose (opcional) |

### Início rápido

```bash
# 1. Clone (abra no DevContainer para o setup completo)
git clone <repo-url> && cd bandkit

# 2. Instale tudo
make setup        # cria venv, instala deps, roda migrations, npm install

# 3. Suba backend + frontend com hot reload
make dev
# → API:  http://localhost:8000/docs
# → App:  http://localhost:5174
```

> **Requer:** Python 3.11+, Node 20+. Docker + DevContainer são opcionais, mas recomendados.

### O que explorei e aprendi

- **UX de modo duplo é um problema de dados, não de UI.** A mesma setlist precisava ser trivial no admin e infalível no palco. Modelar a `MusicalExecution` de forma independente da setlist (para a ordem no palco poder diferir da ordem de planejamento) foi o refactor que destravou isso.
- **Parsear cifras do mundo real é sujo.** PDFs misturam tablatura, diagramas de acordes e marcadores de tom em espanhol (`Tono:`); o parser precisou de heurística e de um fallback de edição manual sempre disponível, em vez de fingir que a extração é perfeita.
- **Espelhe o algoritmo, não o chame.** Reimplementar a transposição em JS no frontend eliminou toda ida à rede na ação de palco mais sensível a latência.
- **DevContainers valem a pena** para um monorepo Python+Node — mas revelam percalços reais (proxy do Vite + port forwarding, CORS, `--host 0.0.0.0`) que o histórico do git documenta.

### Roadmap

- Sincronização em tempo real entre dispositivos (admin avança → músicos acompanham)
- Auto-scroll por tempo (modo teleprompter)
- OCR para PDFs escaneados (não digitais) via Tesseract
- Exportação para PDF / iReal Pro

---

<p align="center"><em>BandKit · Build To Learn portfolio · by David Saggioro</em></p>
